# coding=utf-8
# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import absolute_import, division, print_function, unicode_literals

from pants.backend.python.python_requirement import PythonRequirement
from pants.base.payload import Payload
from pants.base.payload_field import PrimitiveField, PythonRequirementsField
from pants.base.validation import assert_list
from pants.build_graph.target import Target


class PythonRequirementLibrary(Target):
  """A set of pip requirements.

  :API: public
  """

  def __init__(self, payload=None, requirements=None, prepend_to_pythonpath=False, **kwargs):
    """
    :param requirements: pip requirements as `python_requirement <#python_requirement>`_\\s.
    :type requirements: List of python_requirement calls
    """
    payload = payload or Payload()

    assert_list(requirements, expected_type=PythonRequirement, key_arg='requirements')
    assert isinstance(prepend_to_pythonpath, bool)
    payload.add_fields({
      'requirements': PythonRequirementsField(requirements or []),
      'prepend_to_pythonpath': PrimitiveField(prepend_to_pythonpath),
    })
    super(PythonRequirementLibrary, self).__init__(payload=payload, **kwargs)

  @property
  def requirements(self):
    return self.payload.requirements

  @property
  def prepend_to_pythonpath(self):
    return self.payload.prepend_to_pythonpath
