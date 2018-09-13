# coding=utf-8
# Copyright 2018 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

from pants.build_graph.address import Address
from pants.engine.addressable import BuildFileAddresses
from pants.engine.build_files import UnhydratedStruct
from pants.engine.console import Console
from pants.engine.rules import console_rule
from pants.engine.selectors import Get, Select
from pants.base.specs import (DescendantAddresses, Specs)


@console_rule('list', [Select(Console), Select(BuildFileAddresses)])
def fast_list(console, addresses):
  """A fast variant of `./pants list` with a reduced feature set."""
  for address in addresses.dependencies:
    console.print_stdout(address.spec)


@console_rule('dependees', [Select(Console), Select(BuildFileAddresses)])
def fast_dependees(console, addresses):
  """A fast variant of `./pants dependees` with a reduced feature set."""

  all_addresses = yield Get(BuildFileAddresses, Specs((DescendantAddresses(''),)))
  all_targets = yield [Get(UnhydratedStruct, Address, a) for a in all_addresses.addresses]

  dependency_addresses = set(addresses.dependencies)

  # TODO: Bending over backwards here to use UnhydratedStruct.
  for target in all_targets:
    if any(Address.parse(target_dep, relative_to=target.address.spec_path) in dependency_addresses
           for target_dep in target.struct.dependencies):
      console.print_stdout(target.address.spec)
