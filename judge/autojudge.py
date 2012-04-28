#!/usr/bin/python
import importlib
import json
import time

import config

class Judge:
  '''The entity that communicates with the server.'''
  
  def __init__(self):
    '''Initialize the auto grader.'''
    js = config.call(action='initialize_judge')
    if not js['success']:
      raise Exception('Failed to initialize judge.');
    self.judge_id = int(js['judge_id'])
    self.contest_id = int(js['contest_id'])
    
  def fetch_task(self):
    '''Fetch a new grading task.'''
    js = config.call(action='fetch_task', judge_id=self.judge_id, contest_id=self.contest_id)
    if not js['success']:
      raise Exception('Task not successfully fetched.');
    return js
    
  def submit_judgment(self, judgment_id, correct, metadata):
    '''Submits the result of the grading task.'''
    js = config.call(action='submit_judgment', judgment_id=judgment_id, judge_id=self.judge_id, correct=correct, metadata=json.dumps(metadata, separators=(',',':')))
    if not js['success']:
      raise Exception('Judgment not successfully submitted.');
    return js
    
  def __str__(self):
    return 'judge_id %d, contest_id %d' % (self.judge_id, self.contest_id)

if __name__ == '__main__':
  judge = Judge()
  print time.strftime('[%H:%M:%S]:', time.localtime()),
  print 'Initialized judge to %s' % judge
  
  while True:
    print time.strftime('[%H:%M:%S]:', time.localtime()),
    task = judge.fetch_task()
    task_type = task['task_type']
    if task_type == 'grade':
      print 'grading run_id %s (team %s, problem %s) of type %s' % (task['run_id'], task['team_username'], task['alias'], task['problem_type'])
      module = importlib.import_module('modules.' + task['problem_type'])
      (correct, metadata) = module.grade(judge, task)
      judge.submit_judgment(task['judgment_id'], correct, metadata)
    elif task_type == 'reset':
      judge = Judge()
      print 'reset judge to %s' % judge
    elif task_type == 'reset':
      judge = Judge()
      
    elif task_type == 'poll':
      print 'no tasks.'
      time.sleep(config.poll_interval)