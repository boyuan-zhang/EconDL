import torch
import sys
import os
from EconDL.Run import Run
from EconDL.Evaluation import Evaluation

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print('Device', device)

# Experiment name is the command-line argument
run_name = sys.argv[1]
num_experiments = int(sys.argv[2])

folder_path = f'results/{run_name}'
if os.path.isdir(folder_path) == False:
  os.mkdir(folder_path)
  print(f'Folder made at {folder_path}')
else:
  print(f'Folder at {folder_path} already exists')

# Instantiate the Run:
# - Creates a new folder
# - Reads the run's configuration json file
# - Instantiates the experiments with the corresponding nn_hyps
# - Loads the data into the RunObj


# If we are doing this in parallel, then we pass in the job_id parameter here

task_id = int(os.environ.get('SLURM_ARRAY_TASK_ID')) - 1
repeat = task_id

# Train the specific experiment_id and speciifc repeat_id
RunObj = Run(run_name, device, experiment_id = 0, job_id = repeat)
if repeat == 0:
  RunObj.train_benchmarks()
  RunObj.train_multi_forecast_benchmarks()
RunObj.train_ml_experiments()


### Evaluating
# If we are doing this in parallel, then we pass in the job_id parameter here
# RunObj = Run(run_name, device)

# EvaluationObj = Evaluation(RunObj)
# EvaluationObj.Run.compute_conditional_irfs()

# print(EvaluationObj.check_results_sizes())
# EvaluationObj.plot_all()


'''
Note: 
- To run a parallel run, set job_id to the SLURM ID
- If we are evaluating results from a parallel run, set job_id to None, comment out train_all, and uncomment compile_experiments()
'''