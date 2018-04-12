# coding=utf-8
# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)


import re

from pants.build_graph.address import Address
from pants.engine.addressable import OptionalAddress
from pants.engine.mapper import AddressFamily, AddressMapper
from pants.util.objects import datatype, Collection
from pants.engine.rules import rule
from pants.engine.selectors import Get, Select, SelectDependencies
from pants.base.project_tree import Dir
from pants.engine.fs import PathGlobs, Snapshot
from os import sep as os_sep
from os.path import join as os_path_join
from pants.engine.isolated_process import ExecuteProcessResult, ExecuteProcessRequest


class JVMPackageName(datatype('JVMPackageName', ['name'])):
  """A typedef to represent a fully qualified JVM package name."""


class JVMImports(Collection.of(JVMPackageName)):
  pass


class SourceRoots(datatype('SourceRoots', ['srcroots'])):
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
    raise ValueError('Multiple targets might be able to provide {}:\n  {}'.format(
      jvm_package_name, '\n  '.join(str(a) for a in addresses)))
  yield OptionalAddress(addresses[0].to_address())


# TODO: Represents a silly heuristic for computing a package for an import: everything up
# to the first underscore or capitalized token is the package.
_PACKAGE_RE = re.compile(r'^(.*?)\.[A-Z_]')


@rule(JVMImports, [Select(Snapshot)])
def extract_imports(snapshot):
  # TODO
  cmd = tuple(['/Users/stuhood/src/pants/extractimports'] + [f.path for f in snapshot.files])
  result = yield Get(ExecuteProcessResult,
                     ExecuteProcessRequest(cmd, [], snapshot.fingerprint, snapshot.digest_length))
  if result.exit_code:
    raise Exception('Import extraction `{}` failed ({}):\n{}'.format(
      ' '.join(cmd), result.exit_code, result.stderr))

  def packages():
    matched = set()
    for p in result.stdout.splitlines():
      match = _PACKAGE_RE.match(p.strip())
      if match:
        yield JVMPackageName(match.group(1))

  yield JVMImports(set(packages()))


def create_dep_inference_rules():
  """Create rules to execute dep inference for JVM targets."""
  return [
    select_package_address,
    extract_imports,
  ]
