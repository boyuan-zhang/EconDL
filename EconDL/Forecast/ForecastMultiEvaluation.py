import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import cm, colors
import colorcet as cc
import seaborn as sns
import os

from sklearn.metrics import mean_absolute_error

palette = sns.color_palette(cc.glasbey, n_colors = 30)

class ForecastMultiEvaluation:

  def __init__(self, run_name, multi_forecasting_params, Y_train, Y_test):
    
    self.run_name = run_name
    self.folder_path = f'results/{self.run_name}'
    self.image_folder_path = f'{self.folder_path}/images'

    self.Y_train = Y_train
    self.Y_test = Y_test
    self.Y_all = np.concatenate([Y_train, Y_test], axis = 0)

    self.h = multi_forecasting_params['forecast_horizons']
    self.test_size = multi_forecasting_params['test_size'] #T
    self.reestimation_window = multi_forecasting_params['reestimation_window']
    self.R = int(self.test_size / self.reestimation_window)

    self.dataset_name = multi_forecasting_params['dataset_name']
    self.exclude_last = multi_forecasting_params['exclude_last']
    self.exclude_2020 = multi_forecasting_params['exclude_2020']
    self.first_test_id_to_exclude = None

    self.n_var = multi_forecasting_params['n_var']
    self.var_names = multi_forecasting_params['var_names']

    self.benchmarks = multi_forecasting_params['benchmarks']
    self.experiments_names = []
    self.M_varnn = multi_forecasting_params['M_varnn']
    self.normalize_errors_to_benchmark = multi_forecasting_params.get('normalize_errors_to_benchmark', True)

    # Y_pred_big and Y_pred_big_latest are of shape (M, h, n_var, T, R), indexed by the time when the prediction was made
    self.Y_pred_big = None
    self.Y_pred_big_latest = None

    # Y_pred_big_shifted_latest is of shape (M, h, n_var, T), indexed by the time which the prediction was MADE FOR - i.e. shifted forward by h periods
    self.Y_pred_big_shifted_latest = None


    self._load_results()
    if self.exclude_2020 == True:
      self.exclude_2020_results()
  
  def exclude_2020_results(self):
    if self.dataset_name == 'monthly_new':
      test_indices_to_exclude = [(self.test_size + i) for i in range(-31, -19, 1)]
    elif self.dataset_name == 'quarterly_new':
      test_indices_to_exclude = [(self.test_size + i) for i in range(-10, -6, 1)]

    test_indices_to_include = [e for e in range(self.test_size) if e not in test_indices_to_exclude]
    self.first_test_id_to_exclude = min(test_indices_to_exclude)
    print('test_indices_to_exclude', test_indices_to_exclude)
    print('test_indices_to_include', test_indices_to_include)

    self.Y_pred_big = self.Y_pred_big[:, :, :, test_indices_to_include, :]
    self.Y_pred_big_latest = self.Y_pred_big_latest[:, :, :, test_indices_to_include]
    self.Y_pred_big_latest_shifted = self.Y_pred_big_latest_shifted[:, :, :, test_indices_to_include]
    print('Multiforecasting Evaluation after excluding 2020, Y_pred_big shape: ', self.Y_pred_big.shape, 'Y_pred_big_latest shape: ', self.Y_pred_big_latest.shape, 
      'Y_pred_big_latest_shifted shape: ', self.Y_pred_big_latest_shifted.shape)

  def _load_results(self): 

    # Load multi-forecasting results
    experiments_names = []

    # M_total x horizon x variable x bootstraps x test x re-estimation window
    Y_pred_big = np.zeros((self.M_varnn + len(self.benchmarks), 
      self.h+1, self.n_var, self.test_size, self.R))

    # Load all the betas from different experiments
    for i in range(self.M_varnn):

      if os.path.exists(f'{self.folder_path}/multi_fcast_params_{i}_compiled.npz') == True:
        out = np.load(f'{self.folder_path}/multi_fcast_params_{i}_compiled.npz')
        results = np.load(f'{self.folder_path}/params_{i}_compiled.npz', allow_pickle=True)['results'].item()
        experiment_name = results['params']['name']

        FCAST = out['fcast']
        experiments_names.append(experiment_name)
        Y_pred = np.nanmedian(FCAST, axis = 2)
        Y_pred_big[i, :,:,:,:] = Y_pred
      else: # If there no multi-forecasting results, then just skip (add the experiment name so that self.experiments_names is the same length as self.M_varnn )
        results = np.load(f'{self.folder_path}/params_{i}_compiled.npz', allow_pickle=True)['results'].item()
        experiment_name = results['params']['name']
        experiments_names.append(f'{experiment_name} - No results')
        
    # Add the benchmark models in
    benchmark_folder_path = f'{self.folder_path}/benchmarks'

    for bid, benchmark in enumerate(self.benchmarks):

      if benchmark in ['XGBoost', 'RF']:  # Load the ML results - different as their results are saved w the ML models
          out = np.load(f'{self.folder_path}/multi_fcast_params_{benchmark}_compiled.npz')
          FCAST = out['fcast']
          Y_pred = np.nanmedian(FCAST, axis = 2)
          Y_pred_big[self.M_varnn + bid, :,:,:,:] = Y_pred
      else:
        FCAST = np.load(f'{benchmark_folder_path}/benchmark_multi_{benchmark}.npz')
        Y_pred_big[self.M_varnn + bid, :,:,:,:] = FCAST[:, :, :, 0:1]

    # Y_pred_big: M_total x horizon x variable x bootstraps x test x re-estimation window
    self.Y_pred_big = Y_pred_big
    self.Y_pred_big_latest = Y_pred_big[:, :, :, :, -1]

    # Conduct the shifting of Y_pred_big_latest to Y_pred_big_latest_shifted so that the predictions are indexed by the time which the prediction was MADE FOR - i.e. shifted forward by h periods
    Y_pred_big_latest_shifted = np.zeros_like(self.Y_pred_big_latest)
    Y_pred_big_latest_shifted[:] = np.nan
    for horizon in range(1, self.Y_pred_big_latest.shape[1]):
      Y_pred_big_latest_shifted[:, horizon, :, horizon:] = self.Y_pred_big_latest[:, horizon, :, :-horizon]
    self.Y_pred_big_latest_shifted = Y_pred_big_latest_shifted

    print('Multiforecasting Evaluation, Y_pred_big shape: ', self.Y_pred_big.shape, 'Y_pred_big_latest shape: ', self.Y_pred_big_latest.shape, 'Y_pred_big_latest_shifted shape: ', self.Y_pred_big_latest_shifted.shape)

    self.experiments_names = experiments_names + self.benchmarks

  def plot_different_horizons_same_model(self):
    n_models = self.Y_pred_big_latest.shape[0]
    fig, ax = plt.subplots(n_models, self.n_var, figsize = (self.n_var * 6, n_models * 4), constrained_layout = True)

    my_cmap = cm.viridis
    my_norm = colors.Normalize(vmin = 0, vmax = self.h)

    # Plot the actual in each model
    for model in range(n_models):
      
      # Plot actual
      for var in range(self.n_var):
        ax[model, var].set_title(f'{self.experiments_names[model]} - {self.var_names[var]}')
        if self.exclude_last > 0:
          ax[model, var].plot(self.Y_test[:-self.exclude_last, var], label = 'Actual', color = 'black')
        else:
          ax[model, var].plot(self.Y_test[:, var], label = 'Actual', color = 'black')
        
        # Draw a vertical line at the point where we excluded data
        if self.exclude_2020 == True:
          ax[model, var].axvline(x = self.first_test_id_to_exclude - 0.5, ls = 'dashed', color = 'black')
      
      # Plot predicted for each horizon
      for horizon in range(1, self.h+1):

        Y_pred_h = np.transpose(self.Y_pred_big_latest_shifted[model, horizon, :, :])

        for var in range(self.n_var):
          if self.exclude_last > 0:
            ax[model, var].plot(Y_pred_h[:-self.exclude_last, var], label = horizon, color = my_cmap(my_norm(horizon)))
          else:
            ax[model, var].plot(Y_pred_h[:, var], label = horizon, color = my_cmap(my_norm(horizon)))
      if var == (self.n_var - 1) and model == 0:
        ax[model, var].legend()

    image_file = f'{self.image_folder_path}/multi_forecast_preds_diff_horizons_each_model.png'
    plt.savefig(image_file)
    print(f'Multi-forecasting Different Horizon Each Model Preds plotted at {image_file}')


  def plot_different_horizons(self):

    fig, ax = plt.subplots(self.h, self.n_var, figsize = (self.n_var * 6, self.h * 4), constrained_layout = True)

    print('Experiments Names', self.experiments_names)
    print('Number of models', self.Y_pred_big_latest.shape[0])

    for horizon in range(1, self.h+1):
      # Plot actual
      for var in range(self.n_var):
        ax[horizon-1, var].set_title(f'{self.var_names[var]}, h = {horizon}')
        if self.exclude_last > 0:
          ax[horizon-1, var].plot(self.Y_test[:-self.exclude_last, var], label = 'Actual', color = 'black')
        else:
          ax[horizon-1, var].plot(self.Y_test[:, var], label = 'Actual', color = 'black')
        
        # Draw a vertical line at the point where we excluded data
        if self.exclude_2020 == True:
          ax[horizon-1, var].axvline(x = self.first_test_id_to_exclude - 0.5, ls = 'dashed', color = 'black')
      
      # Plot predicted
      for model in range(self.Y_pred_big_latest.shape[0]):

        Y_pred_h = np.transpose(self.Y_pred_big_latest_shifted[model, horizon, :, :])

        for var in range(self.n_var):
          if self.exclude_last > 0:
            ax[horizon-1, var].plot(Y_pred_h[:-self.exclude_last, var], label = self.experiments_names[model], color = palette[model], 
                                    ls = 'solid' if model < self.M_varnn else 'dotted')
          else:
            ax[horizon-1, var].plot(Y_pred_h[:, var], label = self.experiments_names[model], color = palette[model],
                                    ls = 'solid' if model < self.M_varnn else 'dotted')
      if var == (self.n_var - 1) and horizon == 1:
        ax[horizon-1, var].legend()
      
      

    image_file = f'{self.image_folder_path}/multi_forecast_preds_diff_horizons.png'
    plt.savefig(image_file)
    print(f'Multi-forecasting Different Horizon Preds plotted at {image_file}')

  def plot_forecast_errors(self):
    
    n_models = self.Y_pred_big_latest.shape[0]
    
    ### Calculate MAE
    Y_test = self.Y_test
    
    test_periods = ['all', 'exclude_2020', 'exclude_2020_and_after']
    
    if self.dataset_name == 'quarterly_new':
      test_obs = {
        'all': list(range(Y_test.shape[0])),
        'exclude_2020': list(range(Y_test.shape[0] - 10)) + list(range(Y_test.shape[0] - 6, Y_test.shape[0])),
        'exclude_2020_and_after': list(range(Y_test.shape[0] - 10))
      }
    elif self.dataset_name == 'monthly_new':
      test_obs = {
        'all': list(range(Y_test.shape[0])),
        'exclude_2020': list(range(Y_test.shape[0] - 31)) + list(range(Y_test.shape[0] - 19, Y_test.shape[0])),
        'exclude_2020_and_after': list(range(Y_test.shape[0] - 31))
      }
      
    errors = np.zeros((n_models, self.test_size, self.h, self.n_var))  
    
    for horizon in range(1, self.h+1):
      # Get actual, predicted and error
      for model in range(n_models):
        Y_pred_h = np.transpose(self.Y_pred_big_latest_shifted[model, horizon, :, :])
        for var in range(self.n_var):
          actual = self.Y_test[:, var]
          pred = Y_pred_h[:, var]
          error = np.abs(actual - pred)
          # Store the errors in the errors array
          errors[model, :, horizon-1, var] = error  


    cum_errors = np.nancumsum(errors, axis = 1)
    cum_error_benchmark = cum_errors[self.M_varnn + 1, :, :, :] # Benchmark is the AR rolling model
    
    mae_df_all = pd.DataFrame()
    # Calculate mean errors for different test periods
    for test_period in test_periods:
      
      errors_test_period = errors[:, test_obs[test_period], :, :]
      
      maes = np.nanmean(errors_test_period, axis = 1)
      maes_reshaped = maes.reshape(maes.shape[0] * maes.shape[1], maes.shape[2])
      mae_df = pd.DataFrame(maes_reshaped,
                  columns = self.var_names
      )
      mae_df['model'] = np.repeat(self.experiments_names, maes.shape[1])
      mae_df['horizon'] = np.tile(np.arange(1, maes.shape[1] + 1), maes.shape[0])
      mae_df['test_period'] = test_period

      # Standardize errors by benchmark model
      if self.normalize_errors_to_benchmark == True:
        normalized_df = pd.DataFrame()
        for horizon in range(1, self.h+1):
          maes_horizon = mae_df.loc[mae_df['horizon'] == horizon, :].copy()
          maes_horizon[self.var_names] = maes_horizon[self.var_names] / maes_horizon.loc[maes_horizon['model'] == self.experiments_names[self.M_varnn + 1], self.var_names].values
          normalized_df = pd.concat([normalized_df, maes_horizon])
        mae_df = normalized_df
      mae_df_all = pd.concat([mae_df_all, mae_df])

    mae_df_all = mae_df_all[['test_period', 'model', 'horizon'] + self.var_names]
    mae_df_all['model_id'] = mae_df_all['model'].apply(lambda x: self.experiments_names.index(x))
    mae_df_all = mae_df_all.sort_values(by = ['test_period', 'horizon', 'model_id'])
    mae_df_all = mae_df_all.drop(columns = ['model_id'])
    # Convert into the format in PGC's papers
    mae_df_all = mae_df_all.melt(['test_period', 'model', 'horizon'], var_name = 'variable', value_name = 'MAE')
    mae_df_all = mae_df_all.sort_values(['test_period', 'variable', 'horizon']).pivot(values = 'MAE',
                                                    index = ['test_period', 'variable', 'horizon'],
                                                    columns = 'model'
    )
    mae_df_all = mae_df_all[self.experiments_names]
    mae_df_all = mae_df_all.reset_index()
    mae_df_all.to_csv(f'{self.image_folder_path}/multi_forecast_errors_all.csv', index = False)