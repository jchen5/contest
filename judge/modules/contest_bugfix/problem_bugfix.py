import difflib
import itertools
import os
import signal
from string import Template
import subprocess
import sys
import time
import tempfile

import utils
from utils import GradingException
import common

# Splits a source code string into lines, removing empty lines
def get_clean_lines(code):
  return [line for line in code.strip().split("\n") if line.strip()]

# Checks if two lines are the same, ignoring trailing whitespace
def has_line_changed(our_line, their_line, extension):
  if extension == "py":
    return our_line.rstrip() != their_line.rstrip()
  else:
    # TODO: Check for semi-colin for Java / C / C++
    return our_line.strip() != their_line.strip()

# Check that exactly one line in the file has changed
def check_changes(our_code, their_code, team_extension):
  our_lines = get_clean_lines(our_code)
  their_lines = get_clean_lines(their_code)
  num_lines_added = len(their_lines) - len(our_lines)
  if num_lines_added > 0:
    raise GradingException('Illegal insertion of lines')
  elif num_lines_added < 0:
    raise GradingException('Illegal removal of lines')
  else:
    num_lines_changed = sum(
      1
      for our_line, their_line
      in itertools.izip(our_lines, their_lines)
      if has_line_changed(our_line, their_line, team_extension))
    if num_lines_changed > 1:
      raise GradingException('%d lines changed (only 1 allowed)' % num_lines_changed)

def _run_tests(task, team_filebase, team_extension, team_filename, metadata, verbose):
  '''Execute judge test cases.'''

  time_limit = utils.languages[team_extension]['executer_time_limit'] * task['problem_metadata']['time_multiplier'] 
  num_test_cases = len(task['problem_metadata']['judge_io'])
  
  check_changes(task['problem_metadata']['judge_bugs'][team_extension], task['payload'], team_extension)

  for index, test_case in enumerate(task['problem_metadata']['judge_io']):
    executer_cmd = utils.languages[team_extension]['executer'].substitute(src_filebase=team_filebase, src_filename=team_filename).split()
    
    stdin = tempfile.TemporaryFile(bufsize=52428800)
    stdin.write(test_case['input'])
    stdin.flush()
    stdin.seek(0)

    stdout = tempfile.TemporaryFile(bufsize=52428800)
    
    if verbose:
      stderr = tempfile.TemporaryFile(bufsize=52428800)
    else:
      stderr = open(os.devnull, 'w')
    
    executer = subprocess.Popen(executer_cmd, stdin=stdin, stdout=stdout, stderr=stderr, preexec_fn=os.setsid, close_fds=True)
    start_time = time.time()
    while executer.poll() is None and (time.time() - start_time <= time_limit):
      time.sleep(0.5)
    if executer.poll() is None:
      if verbose:
        utils.progress('Team executable did not finish; killing PID %d after %d seconds' % (executer.pid, time.time() - start_time))
      os.killpg(executer.pid, signal.SIGKILL)
      raise GradingException('Time limit exceeded')
    if executer.returncode != 0:
      if verbose:
        utils.progress('Team executable gave non-zero return code: %d' % executer.returncode)
        stderr.seek(0)
        print stderr.read()
      raise GradingException('Run time error')
    
    stdout.seek(0)
    team_output = stdout.read()
   
    team_output_lines = map(lambda line: line.strip(), team_output.splitlines())
    judge_output_lines = map(lambda line: line.strip(), test_case['output'].splitlines())
    if team_output_lines != judge_output_lines:
      if verbose:
        utils.progress('Failed %2d / %2d' % (index + 1, num_test_cases))
        diff = difflib.Differ()
        sys.stdout.writelines(list(diff.compare(map(lambda line: line + '\n', team_output_lines), map(lambda line: line + '\n', judge_output_lines))))
      raise GradingException('Incorrect output')
    utils.progress('Passed %2d / %2d' % (index + 1, num_test_cases))
  utils.progress('Correct')
  return True

def grade(q, task, verbose):
  '''Grades a bugfix submission.'''

  return common.grade(q, task, verbose, _run_tests)
