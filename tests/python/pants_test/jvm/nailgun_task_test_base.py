# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.base.deprecated import deprecated_module
from pants.testutil.jvm.nailgun_task_test_base import NailgunTaskTestBase as NailgunTaskTestBase  # noqa


deprecated_module(
  removal_version="1.25.0.dev0",
  hint_message="Import pants.testutil.jvm.nailgun_task_test_base instead."
)
