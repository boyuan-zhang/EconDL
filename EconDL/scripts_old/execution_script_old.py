import numpy as np
import pandas as pd
import torch
import DataHelpers.DataLoader as DataLoader
import DataHelpers.DataProcesser as DataProcesser # possible to combine w dataloader
import IRF.IRFConditional as IRFConditional # @TODO: fix this import (want to put it in a folder) - also create IRF superclass, and IRFConditional and IRFUnconditional subclasses
from IRF.IRFUnconditional import IRFUnconditional
import TrainVARNN 
from Benchmarks import Benchmarks # @TODO: create Benchmark superclass, and VARNNBenchmarks and ForecastBenchmarks subclasses
import ForecastBenchmarks 
import ForecastMulti
import Evaluation

import json
import os
import sys

from exp_config.nn_hyps import nn_hyps_default


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print('device: ', device)

# Experiment name is the command-line argument
run_name = sys.argv[1]

# Read experiment configuration - dataset, parameters: nn_hyps, experiment_settings (num_repeats), evaluation_settings (how to draw graphs etc.)
with open(f'../exp_config/{run_name}.json', 'r') as f:
    run_params = json.load(f)

# Create folder to store results - that is where the results go into
folder_path = f'../results/{run_name}'
if os.path.isdir(folder_path) == False:
  os.mkdir(folder_path)
else:
  print('Folder already exists')

# Add experiment to a running list of experiments I've run

# Load dataset
dataset, run_params = DataLoader.load_data(run_params)

# Get the number of experiments to run
num_experiments = len(run_params['nn_hyps'])
num_repeats = run_params['run_params']['num_repeats']
num_inner_bootstraps = run_params['run_params']['num_inner_bootstraps']


for repeat_id in range(num_repeats):
  for experiment_id in range(num_experiments):

    experiment_params = run_params['nn_hyps'][experiment_id]

    print(f'Experiment {experiment_id}, Params: {experiment_params}')
    nn_hyps = nn_hyps_default.copy()
    nn_hyps.update(experiment_params)
    nn_hyps['num_bootstrap'] = num_inner_bootstraps

    # Process dataset - DONE
    X_train, X_test, Y_train, Y_test, nn_hyps = DataProcesser.process_data_wrapper(dataset, nn_hyps)


    if run_params['execution_params']['varnn_estimation'] == True:
      # Train the VARNN
      print('s_pos', nn_hyps['s_pos'])
      results = TrainVARNN.conduct_bootstrap(X_train, X_test, Y_train, Y_test, nn_hyps, device)

      with open(f'{folder_path}/params_{experiment_id}_repeat_{repeat_id}.npz', 'wb') as f:
          np.savez(f, 
            betas = results['betas_draws'], 
            betas_in = results['betas_in_draws'], 
            sigmas = results['sigmas_draws'], 
            sigmas_in = results['sigmas_in_draws'],
            precision = results['precision_draws'], 
            precision_in = results['precision_in_draws'],
            cholesky = results['cholesky_draws'], 
            cholesky_in = results['cholesky_in_draws'],
            train_preds = results['pred_in_ensemble'] , 
            test_preds = results['pred_ensemble'], 
            y = Y_train, 
            y_test = Y_test, 
            params = nn_hyps)


    if run_params['execution_params']['unconditional_irfs'] == True:

      unconditional_irf_params = {
        'n_lag_linear': nn_hyps['n_lag_linear'],
        'n_lag_d': nn_hyps['n_lag_d'],
        'n_var': len(nn_hyps['var_names']),
        'num_simulations': 600,
        'endh': 40,
        'start_shock_time': 40,
        'forecast_method': 'new', # old or new
        'max_h': 20, 
        'var_names': nn_hyps['var_names'],
        'plot_all_bootstraps': False
      }

      IRFUnconditionalObj = IRFUnconditional(run_name, unconditional_irf_params, device)
      fcast, fcast_cov_mat, sim_shocks = IRFUnconditionalObj.get_irfs_wrapper(Y_train, Y_test, results)

      with open(f'{folder_path}/fcast_params_{experiment_id}_repeat{repeat_id}.npz', 'wb') as f:
        np.savez(f, fcast = fcast, fcast_cov_mat = fcast_cov_mat)

    if run_params['execution_params']['multi_forecasting'] == True:

      multi_forecasting_params = {
        'test_size': 60, 
        'forecast_horizons': 6,
        'reestimation_window': 60,
        'num_inner_bootstraps': num_inner_bootstraps,
        'num_repeats': 1, 

        'n_lag_linear': nn_hyps['n_lag_linear'],
        'n_lag_d': nn_hyps['n_lag_d'],
        'n_var': len(nn_hyps['var_names']),
        'forecast_method': 'new', # old or new
        'var_names': nn_hyps['var_names'],
      }


# Compute benchmarks
benchmark_params = {
  'n_lag_linear': 1, 
  'n_lag_d': 2,
  'benchmarks': ['VAR_whole', 'AR_whole', 'VAR_roll', 'AR_roll', 'VAR_expand', 'AR_expand', 'RF_whole'],
  'var_names': ['DGS3', 'inf', 'unrate'],
  'test_size': 100,
  'window_length': 40,
  'reestimation_window': 1
}
if run_params['execution_params']['benchmarks'] == True:
  BenchmarkObj = Benchmarks(dataset, benchmark_params, run_name)
  BenchmarkObj.compute_benchmarks()


# Compute conditional IRFs (straight from VARNN estimation results) and plot
# @DEV: do conditional IRFs come from 
if run_params['execution_params']['conditional_irfs'] == True:
  irf_cond_results = IRFConditional.compute_IRF()






# # Compute unconditional IRFs (only if there is no time hemisphere!) and plot
# irf_uncond_results = IRFUnconditional.compute_IRF()

# # Compute benchmarks
# benchmark_results = Benchmarks.compute_benchmarks()

# # Do multi-horizon forecasting
# fcast_results = ForecastMulti.get_forecasts()

# # Compute benchmarks for multi-horizon forecasting
# fcast_benchmark_results = ForecastBenchmarks.compute_benchmarks()

# # Evaluation - plot TVPs, betas and sigmas
# Evaluation.evaluate_TVPs(results, benchmark_results)

# # Evaluation - one-step forecasting - compute MSEs (plot graphs of cumulative MSEs)
# Evaluation.evaluate_one_step_forecasts(results, benchmark_results)

# # Evaluation - multi-step forecasting
# Evaluation.evaluate_multi_step_forecasts(results, benchmark_results)