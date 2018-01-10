# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import (absolute_import, division, generators, nested_scopes, print_function,
                        unicode_literals, with_statement)

import os
import sys
from textwrap import dedent
import Queue
import threading
import time

from pants.base.cmd_line_spec_parser import CmdLineSpecParser
from pants.build_graph.address import Address
from pants.engine.fs import PathGlobs
from pants.pantsd.service.fs_event_service import FSEventService
from pants.logging.setup import setup_logging
from pants.util import desktop
from pants.util.contextutil import temporary_file_path
from pants.util.process_handler import subprocess
from pants_test.engine.examples.planners import setup_json_scheduler
from pants_test.engine.util import init_native, init_watchman_launcher


# TODO: These aren't tests themselves, so they should be under examples/ or testprojects/?
def visualize_execution_graph(scheduler, request):
  with temporary_file_path(cleanup=False, suffix='.dot') as dot_file:
    scheduler.visualize_graph_to_file(request, dot_file)
    print('dot file saved to: {}'.format(dot_file))

  with temporary_file_path(cleanup=False, suffix='.svg') as image_file:
    subprocess.check_call('dot -Tsvg -o{} {}'.format(image_file, dot_file), shell=True)
    print('svg file saved to: {}'.format(image_file))
    desktop.ui_open(image_file)


def visualize_build_request(build_root, goals, subjects):
  native = init_native()
  scheduler = setup_json_scheduler(build_root, native)

  execution_request = scheduler.build_request(goals, subjects)
  scheduler.schedule(execution_request)
  visualize_execution_graph(scheduler, execution_request)


def pop_build_root_and_goals(description, args):
  def usage(error_message):
    print(error_message, file=sys.stderr)
    print(dedent("""
    {}
    """.format(sys.argv[0])), file=sys.stderr)
    sys.exit(1)

  if len(args) < 2:
    usage('Must supply at least the build root path and one goal: {}'.format(description))

  build_root = args.pop(0)

  if not os.path.isdir(build_root):
    usage('First argument must be a valid build root, {} is not a directory.'.format(build_root))
  build_root = os.path.realpath(build_root)

  def is_goal(arg): return os.path.sep not in arg

  goals = [arg for arg in args if is_goal(arg)]
  if not goals:
    usage('Must supply at least one goal.')

  return build_root, goals, [arg for arg in args if not is_goal(arg)]


def main_addresses():
  build_root, goals, args = pop_build_root_and_goals(
    '[build root path] [goal]+ [address spec]*', sys.argv[1:])

  cmd_line_spec_parser = CmdLineSpecParser(build_root)
  spec_roots = [cmd_line_spec_parser.parse_spec(spec) for spec in args]
  visualize_build_request(build_root, goals, spec_roots)


def launch_fs_event_service(build_root, watchman):
  lock = threading.RLock()
  queue = Queue.Queue(maxsize=64)

  fs_event_service = FSEventService(watchman, build_root, 1)
  fs_event_service.setup(lock, lock)
  fs_event_service.register_all_files_handler(queue.put)

  t = threading.Thread(target=fs_event_service.run)
  t.daemon = True
  t.start()

  return queue


def main_addresses_loop():
  build_root, goals, args = pop_build_root_and_goals(
    '[build root path] [goal]+ [address spec]*', sys.argv[1:])

  cmd_line_spec_parser = CmdLineSpecParser(build_root)
  spec_roots = [Address.parse(spec) for spec in args]
  setup_logging('DEBUG', console_stream=sys.stderr)
  native = init_native()
  watchman_launcher = init_watchman_launcher()
  watchman_launcher.maybe_launch()
  scheduler = setup_json_scheduler(build_root, native)
  fs_event_queue = launch_fs_event_service(build_root, watchman_launcher.watchman)

  # Repeatedly re-execute, waiting on an instance of watchman in between.
  execution_request = scheduler.build_request(goals, spec_roots)
  start = time.time()
  while True:
    # Run once.
    result = scheduler.execute(execution_request).root_products[0][1]
    print('>' * 100)
    print('>>> Completed request in {} seconds: {}'.format(time.time() - start, result))
    print('>' * 100)
    # Wait for a filesystem invalidation event.
    while True:
      try:
        invalidated = 0
        event = fs_event_queue.get(timeout=1)
        start = time.time()
        if not event['is_fresh_instance']:
          files = [f.decode('utf-8') for f in event['files']]
          invalidated = scheduler.invalidate_files(files)
        fs_event_queue.task_done()
        if invalidated:
          break
      except Queue.Empty:
        continue


def main_filespecs():
  build_root, goals, args = pop_build_root_and_goals(
    '[build root path] [filespecs]*', sys.argv[1:])

  # Create PathGlobs for each arg relative to the buildroot.
  path_globs = PathGlobs.create('', include=args, exclude=[])
  visualize_build_request(build_root, goals, path_globs)
