# coding=utf-8
# Copyright 2016 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import logging
from collections import namedtuple

from pants.base.build_environment import get_buildroot, get_scm
from pants.base.file_system_project_tree import FileSystemProjectTree
from pants.base.specs import DescendantAddresses, Spec
from pants.bin.options_initializer import OptionsInitializer
from pants.build_graph.address import Address
from pants.engine.engine import LocalSerialEngine
from pants.engine.fs import create_fs_tasks
from pants.engine.graph import create_graph_tasks
from pants.engine.legacy.address_mapper import LegacyAddressMapper
from pants.engine.legacy.change_calculator import EngineChangeCalculator
from pants.engine.legacy.graph import LegacyBuildGraph, LegacyTarget, create_legacy_graph_tasks
from pants.engine.legacy.parser import LegacyPythonCallbacksParser
from pants.engine.legacy.spec_parser import EngineCmdLineSpecParser
from pants.engine.legacy.structs import (JvmAppAdaptor, PythonTargetAdaptor, RemoteSourcesAdaptor,
                                         TargetAdaptor)
from pants.engine.mapper import AddressMapper
from pants.engine.parser import SymbolTable
from pants.engine.scheduler import LocalScheduler
from pants.engine.storage import Storage
from pants.option.options_bootstrapper import OptionsBootstrapper
from pants.util.memo import memoized_method


logger = logging.getLogger(__name__)


# N.B. This should be top-level in the module for pickleability - don't nest it.
class LegacySymbolTable(SymbolTable):
  """A v1 SymbolTable facade for use with the v2 engine."""

  @classmethod
  @memoized_method
  def aliases(cls):
    """TODO: This is a nasty escape hatch to pass aliases to LegacyPythonCallbacksParser."""
    _, build_config = OptionsInitializer(OptionsBootstrapper()).setup(init_logging=False)
    return build_config.registered_aliases()

  @classmethod
  @memoized_method
  def table(cls):
    aliases = {alias: TargetAdaptor for alias in cls.aliases().target_types}
    # TODO: The alias replacement here is to avoid elevating "TargetAdaptors" into the public
    # API until after https://github.com/pantsbuild/pants/issues/3560 has been completed.
    # These should likely move onto Target subclasses as the engine gets deeper into beta
    # territory.
    aliases['jvm_app'] = JvmAppAdaptor
    aliases['remote_sources'] = RemoteSourcesAdaptor
    for alias in ('python_library', 'python_tests', 'python_binary'):
      aliases[alias] = PythonTargetAdaptor

    return aliases


class LegacyGraphHelper(namedtuple('LegacyGraphHelper', ['scheduler', 'engine', 'symbol_table_cls',
                                                         'change_calculator'])):
  """A container for the components necessary to construct a legacy BuildGraph facade."""

  class InvalidSpecConstraint(Exception):
    """Raised when invalid constraints are given via target specs and arguments like --changed*."""

  def _to_v1_target_specs(self, spec_roots):
    """Given v2 spec roots, produce v1 compatible specs."""
    for spec in spec_roots:
      if isinstance(spec, Spec):
        yield spec.to_spec_string()
      elif isinstance(spec, Address):
        yield spec.spec
      else:
        raise TypeError('unsupported spec type `{}` when converting {!r} to v1 spec'
                        .format(type(spec), spec))

  def _determine_spec_roots(self, changed_request, spec_roots):
    """Determines the spec roots/target roots for a given request."""
    logger.debug('spec_roots is: %s', spec_roots)
    logger.debug('changed_request is: %s', changed_request)

    # TODO: Kill v1_spec_roots once `LegacyAddressMapper.specs_to_addresses()` exists.
    if changed_request and changed_request.is_actionable():
      if spec_roots:
        # We've been provided spec roots (e.g. `./pants list ::`) AND a changed request. Error out.
        raise self.InvalidSpecConstraint('cannot provide changed parameters and target specs!')
      else:
        # We've been provided no spec roots (e.g. `./pants list`) AND a changed request. Compute
        # alternate target roots.
        changed = self.change_calculator.changed_target_addresses(changed_request)
        logger.debug('changed addresses: %s', changed)
        return list(self._to_v1_target_specs(changed)), changed
    else:
      if spec_roots:
        # We've been provided spec_roots (e.g. `./pants list ::`) and no changed request. Proxy.
        return list(self._to_v1_target_specs(spec_roots)), spec_roots
      else:
        # We've been provided no spec_roots (e.g. `./pants list`) and no changed request. Translate.
        return ['::'], [DescendantAddresses('')]

  def warm_product_graph(self, spec_roots, changed_request=None):
    """Warm the scheduler's `ProductGraph` with `LegacyTarget` products.

    :param list spec_roots: A list of `Spec` instances representing the root targets of the request.
    :param ChangedRequest changed_request: A ChangedRequest for determining alternate target roots.
    """
    _, spec_roots = self._determine_spec_roots(changed_request, spec_roots)
    logger.debug('v2_spec_roots are: %s', spec_roots)
    request = self.scheduler.execution_request([LegacyTarget], spec_roots)
    result = self.engine.execute(request)
    if result.error:
      raise result.error

  def create_build_graph(self, spec_roots, build_root=None, changed_request=None):
    """Construct and return a `BuildGraph` given a set of input specs.

    :param list spec_roots: A list of `Spec` instances representing the root targets of the request.
    :param string build_root: The build root.
    :param ChangedRequest changed_request: A ChangedRequest for determining alternate target roots.
    :returns: A tuple of (BuildGraph, AddressMapper, list[specs]).
    """
    v1_spec_roots, v2_spec_roots = self._determine_spec_roots(changed_request, spec_roots)
    logger.debug('v1_spec_roots are: %s', v1_spec_roots)
    logger.debug('v2_spec_roots are: %s', v2_spec_roots)

    graph = LegacyBuildGraph(self.scheduler, self.engine, self.symbol_table_cls)
    logger.debug('build_graph is: %s', graph)
    with self.scheduler.locked():
      # Ensure the entire generator is unrolled.
      for _ in graph.inject_specs_closure(v2_spec_roots):
        pass

    logger.debug('engine cache stats: %s', self.engine.cache_stats())
    address_mapper = LegacyAddressMapper(graph, build_root or get_buildroot())
    logger.debug('address_mapper is: %s', address_mapper)
    return graph, address_mapper, v1_spec_roots


class EngineInitializer(object):
  """Constructs the components necessary to run the v2 engine with v1 BuildGraph compatibility."""

  @staticmethod
  def parse_commandline_to_spec_roots(options=None, args=None, build_root=None):
    if not options:
      options, _ = OptionsInitializer(OptionsBootstrapper(args=args)).setup(init_logging=False)
    cmd_line_spec_parser = EngineCmdLineSpecParser(build_root or get_buildroot())
    spec_roots = [cmd_line_spec_parser.parse_spec(spec) for spec in options.target_specs]
    return spec_roots

  @staticmethod
  def setup_legacy_graph(pants_ignore_patterns,
                         symbol_table_cls=None,
                         build_ignore_patterns=None,
                         exclude_target_regexps=None):
    """Construct and return the components necessary for LegacyBuildGraph construction.

    :param list pants_ignore_patterns: A list of path ignore patterns for FileSystemProjectTree,
                                       usually taken from the '--pants-ignore' global option.
    :param SymbolTable symbol_table_cls: A SymbolTable class to use for build file parsing, or
                                         None to use the default.
    :param list build_ignore_patterns: A list of paths ignore patterns used when searching for BUILD
                                       files, usually taken from the '--build-ignore' global option.
    :param list exclude_target_regexps: A list of regular expressions for excluding targets.
    :returns: A tuple of (scheduler, engine, symbol_table_cls, build_graph_cls).
    """

    build_root = get_buildroot()
    scm = get_scm()
    project_tree = FileSystemProjectTree(build_root, pants_ignore_patterns)
    symbol_table_cls = symbol_table_cls or LegacySymbolTable

    # Register "literal" subjects required for these tasks.
    # TODO: Replace with `Subsystems`.
    address_mapper = AddressMapper(symbol_table_cls=symbol_table_cls,
                                   parser_cls=LegacyPythonCallbacksParser,
                                   build_ignore_patterns=build_ignore_patterns,
                                   exclude_target_regexps=exclude_target_regexps)

    # Create a Scheduler containing graph and filesystem tasks, with no installed goals. The
    # LegacyBuildGraph will explicitly request the products it needs.
    tasks = (
      create_legacy_graph_tasks(symbol_table_cls) +
      create_fs_tasks() +
      create_graph_tasks(address_mapper, symbol_table_cls)
    )

    scheduler = LocalScheduler(dict(), tasks, project_tree)
    # TODO: Do not use the cache yet, as it incurs a high overhead.
    engine = LocalSerialEngine(scheduler, Storage.create(), use_cache=False)
    spec_parser = EngineCmdLineSpecParser(build_root)
    change_calculator = EngineChangeCalculator(engine, spec_parser, scm) if scm else None

    return LegacyGraphHelper(scheduler, engine, symbol_table_cls, change_calculator)
