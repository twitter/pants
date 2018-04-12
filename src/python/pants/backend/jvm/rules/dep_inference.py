# coding=utf-8
# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import re
from os import sep as os_sep
from os.path import join as os_path_join

from pants.base.project_tree import Dir
from pants.engine.addressable import OptionalAddress
from pants.engine.fs import PathGlobs, Snapshot
from pants.engine.isolated_process import ExecuteProcessRequest, ExecuteProcessResult
from pants.engine.legacy.graph import HydratedField, ScalaSourcesField, _eager_fileset_with_spec
from pants.engine.mapper import AddressFamily
from pants.engine.rules import SingletonRule, rule
from pants.engine.selectors import Get, Select
from pants.option.global_options import GlobMatchErrorBehavior
from pants.util.objects import Collection, datatype


logger = logging.getLogger(__name__)


class JVMPackageName(datatype(['name'])):
  """A typedef to represent a fully qualified JVM package name."""


class JVMImports(Collection.of(JVMPackageName)):
  pass


class SourceRoots(datatype(['srcroots'])):
  """Placeholder for the SourceRoot subsystem."""


@rule(OptionalAddress, [Select(JVMPackageName), Select(SourceRoots)])
def select_package_address(jvm_package_name, source_roots):
  """Return the Address from the given AddressFamilies which provides the given package."""

  # Locate candidate directories for the package.
  rel_package_dir = jvm_package_name.name.replace('.', os_sep)
  candidate_dir_specs = tuple(os_path_join(srcroot, rel_package_dir)
                              for srcroot in source_roots.srcroots)
  candidate_dirs = yield Get(Snapshot, PathGlobs(include=candidate_dir_specs))

  # And collect addresses in those directories.
  address_families = yield [Get(AddressFamily, Dir, d) for d in candidate_dirs.dir_stats]
  addresses = [address for address_family in address_families
                       for address in address_family.addressables.keys()]
  if len(addresses) == 0:
    yield OptionalAddress(None)
  if len(addresses) > 1:
    logger.debug('Multiple targets might be able to provide {}:\n  {}'.format(
      jvm_package_name, '\n  '.join(str(a) for a in addresses)))
  yield OptionalAddress(addresses[0].to_address())


# TODO: Represents a silly heuristic for computing a package for an import: everything up
# to the first underscore or capitalized token is the package.
_PACKAGE_RE = re.compile(r'^(.*?)\.[A-Z_]')


@rule(JVMImports, [Select(Snapshot)])
def extract_imports(snapshot):
  # TODO
  cmd = tuple(['/Users/stuhood/src/pants/extractimports'] + [f.path for f in snapshot.files])
  execute_process_request = ExecuteProcessRequest(
      argv=cmd,
      input_files=snapshot.directory_digest,
      description='Extract imports',
    )
  result = yield Get(ExecuteProcessResult, ExecuteProcessRequest, execute_process_request)

  def packages():
    for p in result.stdout.splitlines():
      match = _PACKAGE_RE.match(p.strip())
      if match:
        yield JVMPackageName(match.group(1))

  yield JVMImports(set(packages()))


@rule(HydratedField, [Select(ScalaSourcesField), Select(GlobMatchErrorBehavior)])
def hydrate_scala_sources(sources_field, glob_match_error_behavior):
  """Given a ScalaSourcesField, request a Snapshot for its path_globs and create an EagerFilesetWithSpec."""

  path_globs = sources_field.path_globs.copy(glob_match_error_behavior=glob_match_error_behavior)
  snapshot = yield Get(Snapshot, PathGlobs, path_globs)
  jvm_imports = yield Get(JVMImports, Snapshot, snapshot)
  optional_addresses = yield [Get(OptionalAddress, JVMPackageName, i)
                              for i in jvm_imports.dependencies]
  dependencies = tuple(a.value for a in optional_addresses if a.value)
  fileset_with_spec = _eager_fileset_with_spec(sources_field.address.spec_path,
                                               sources_field.filespecs,
                                               snapshot)
  yield HydratedField(sources_field.arg, fileset_with_spec, dependencies)


def create_dep_inference_rules():
  """Create rules to execute dep inference for JVM targets."""
  return [
    select_package_address,
    extract_imports,
    hydrate_scala_sources,
    # TODO: Hardcoded. Would want to configure with a Subsystem instead.
    SingletonRule(SourceRoots, SourceRoots(('3rdparty/jvm', 'src/java', 'src/scala'))),
  ]
