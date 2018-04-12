# coding=utf-8
# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)


from pants.build_graph.address import Address
from pants.engine.mapper import AddressFamily, AddressMapper
from pants.util.objects import datatype
from pants.util.objects import Collection
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


@rule(Address, [Select(JVMPackageName), Select(SourceRoots)])
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
    raise ValueError('No targets existed in {} to provide {}'.format(
      address_families, jvm_package_name))
  elif len(addresses) > 1:
    raise ValueError('Multiple targets might be able to provide {}:\n  {}'.format(
      jvm_package_name, '\n  '.join(str(a) for a in addresses)))
  yield addresses[0].to_address()


@rule(JVMImports, [Select(Snapshot)])
def extract_imports(snapshot):
  # TODO
  cmd = tuple(['/Users/stuhood/src/pants/extractimports'] + [f.path for f in snapshot.files])
  result = yield Get(ExecuteProcessResult,
                     ExecuteProcessRequest(cmd, [], snapshot.fingerprint, snapshot.digest_length))
  if result.exit_code:
    raise Exception('Import extraction `{}` failed ({}):\n{}'.format(
      ' '.join(cmd), result.exit_code, result.stderr))

  yield JVMImports(tuple(JVMPackageName(p.strip()) for p in result.stdout.splitlines()))


def create_dep_inference_rules():
  """Create rules to execute dep inference for JVM targets."""
  return [
    select_package_address,
    extract_imports,
  ]
