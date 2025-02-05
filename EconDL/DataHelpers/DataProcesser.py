import numpy as np 
from EconDL.utils import get_bootstrap_indices


def process_data(data, nn_hyps, marx = True, test_size = 60, n_time_trends = 0, time_dummy_setting = 0, dummy_interval = 12):

  n_var = data.shape[1]
  var_name = list(data.columns)
  data = data.copy()

  n_lag_d = nn_hyps['n_lag_d']
  n_lag_linear = nn_hyps['n_lag_linear']
  n_lag_ps = nn_hyps['n_lag_ps']

  # 2: Generating the lags
  for lag in range(1, n_lag_d + 1):
    for col in var_name:
      data[f'{col}.l{lag}'] = data[col].shift(lag)

  data = data.dropna()

  y_mat = np.array(data.iloc[:, :n_var]) # Target vairables (n_vars)
  x_mat = np.array(data.iloc[:, n_var:]) # Explanatory variables (lags of target variables + other exogenous variables)
  x_mat_colnames = data.iloc[:, n_var:].columns
  
  if marx == True:
    # Computing MARX (moving averages)
    x_mat_marx = np.array(x_mat)

    # for lag in range(2, n_lag_d + 1):
    #   for var in range(n_var):
    #     # For earlier lags, set earliest lagged value to be the mean of all more recent lags
    #     who_to_avg = list(range(var, n_var * (lag - 1) + var + 1, n_var))
    #     x_mat_marx[:, who_to_avg[-1]] = x_mat[:, who_to_avg].mean(axis = 1)

    x_mat_marx_colnames = ['Nonlinear_' + e for e in x_mat_colnames]
    print('Size of x_mat before appending Nonlinear', x_mat[:, :(n_var * n_lag_linear)].shape)
    print('Size of x_mat_marx', x_mat_marx.shape)

    # Concatenate
    x_mat_all = np.hstack([x_mat[:, :(n_var * n_lag_linear)], x_mat_marx])
    x_mat_all_colnames = list(x_mat_colnames[:(n_var * n_lag_linear)]) + list(x_mat_marx_colnames)

    print('x_mat_all size', x_mat_all.shape)

  
  else: # If no MARX
    x_mat_all = np.array(x_mat)
    x_mat_all = x_mat_all[:, :(n_var * n_lag_d)]

  print('x_mat_all size', x_mat_all.shape)

  # Add exog
  if nn_hyps['exog'] is not None:
    x_mat_all = np.hstack([x_mat_all, nn_hyps['exog'][n_lag_d:, :]])
    print('Appended exogenous data', nn_hyps['exog'].shape)
  size_before_time = x_mat_all.shape[1]

  ### Create time dummies based on different methods

  if time_dummy_setting == 0: # Linear + Quad + Cubic time trend
    time_trends = np.zeros((x_mat_all.shape[0], 3))
    time_trends[:, 0] = np.array(list(range(x_mat_all.shape[0])))
    time_trends[:, 1] = time_trends[:, 0] ** 2
    time_trends[:, 2] = time_trends[:, 0] ** 3

    # Add time trend
    for i in range(n_time_trends):
      x_mat_all = np.hstack([x_mat_all, time_trends])

  elif time_dummy_setting == 1: # Time dummies (1/0, no overlap)
    # Get number of time dummies to make - dummies every 60 months  (5 years)
    n_dummies = int(x_mat_all.shape[0] / dummy_interval)
    time_dummies = np.zeros((x_mat_all.shape[0], n_dummies))
    for i in range(n_dummies):
      for t in range(x_mat_all.shape[0]):
        time_dummies[t, i] = 1 if ( int(t / dummy_interval) == i) else 0
    
    x_mat_all = np.hstack([x_mat_all, time_dummies])

  elif time_dummy_setting == 2: # PGCtime dummies (1/0, overlapping)
    # Get number of time dummies to make - dummies every 60 months  (5 years)
    n_dummies = int(x_mat_all.shape[0] / dummy_interval)
    time_dummies = np.ones((x_mat_all.shape[0], n_dummies))
    for i in range(n_dummies):
      for t in range(x_mat_all.shape[0]):
        time_dummies[t, i] = 0 if ( int(t / dummy_interval) <= i) else 1

    random_mat = np.random.randn(x_mat_all.shape[0], n_dummies) * 0.001
    time_dummies = time_dummies + random_mat
    x_mat_all = np.hstack([x_mat_all, time_dummies])

  elif time_dummy_setting == 3: # Both time dummies and time trends 
  # (essentially settings 0 and 1 combined)
    time_trends = np.zeros((x_mat_all.shape[0], 3))
    time_trends[:, 0] = np.array(list(range(x_mat_all.shape[0])))
    time_trends[:, 1] = time_trends[:, 0] ** 2
    time_trends[:, 2] = time_trends[:, 0] ** 3
    for i in range(n_time_trends):
      x_mat_all = np.hstack([x_mat_all, time_trends])

    # Get number of time dummies to make - dummies every 60 months  (5 years)
    n_dummies = int(x_mat_all.shape[0] / dummy_interval)
    time_dummies = np.zeros((x_mat_all.shape[0], n_dummies))
    for i in range(n_dummies):
      for t in range(x_mat_all.shape[0]):
        time_dummies[t, i] = 1 if ( int(t / dummy_interval) == i) else 0
    x_mat_all = np.hstack([x_mat_all, time_dummies])

  elif time_dummy_setting == 4: # Only linear trend
    time_trends = np.zeros((x_mat_all.shape[0], 1))
    time_trends[:, 0] = np.array(list(range(x_mat_all.shape[0])))
    for i in range(n_time_trends):
      x_mat_all = np.hstack([x_mat_all, time_trends])

  print('Size of X_train afer appending time', x_mat_all.shape, f'Time dummy setting: {time_dummy_setting}')

  # Train-test split
  X_train = x_mat_all[:-test_size, :]
  X_test = x_mat_all[-test_size:, :]
  Y_train = y_mat[:-test_size, :]
  Y_test = y_mat[-test_size:, :]

  # If time dummies, set test time dummy values to the same as the last value
  if time_dummy_setting in [1,2,3]:
    X_test[:, size_before_time:] = X_train[-1, size_before_time:]

  # Get the index of the lagged values of unemployment rate
  first_parts = ['.l' + str(lag) for lag in range(1, n_lag_linear + 1)]
  first_parts_ps = ['.l' + str(lag) for lag in range(1, n_lag_ps + 1)]

  get_xpos = lambda variable_name, first_parts: [list(i for i, n in enumerate(x_mat_all_colnames) if n == variable_name + first_part)[0] for first_part in first_parts]

  x_pos = {}
  for var in var_name:
    x_pos[var] = get_xpos(var, first_parts)

  print('x_pos', x_pos)

  # Put x_pos back into the list (NN function needs it like that for now)
  x_pos = list(x_pos.values())

  if nn_hyps['prior_shift'] == True:
    x_pos_ps = {}
    for var in var_name:
      x_pos_ps[var] = get_xpos(var, first_parts_ps)
    x_pos_ps = list(x_pos_ps.values())
  else:
    x_pos_ps = None

  # Only input the time trend into nonlinear part
  nn_hyps.update({'x_pos': x_pos, 
                  'x_pos_ps': x_pos_ps})
  print('Size of X_train', X_train.shape)

  return X_train, X_test, Y_train, Y_test, x_mat_all, y_mat, nn_hyps

def process_data_wrapper(data, nn_hyps):

    # nn_hyps needed: test_size, variables, num_bootstrap, time_dummy_setting, marx, dummy_interval, s_pos, s_pos_setting, model

    test_size = nn_hyps['test_size']
    max_test_size = nn_hyps['max_test_size']
    variable_list = nn_hyps['var_names']

    # Subset variables
    x_d = data[variable_list]
    x_d_colnames = x_d.columns
    var_names = x_d.columns
    n_var = len(var_names)

    # Get the bootstraps
    if nn_hyps['model'] == 'VARNN':
      if nn_hyps['same_train'] == True:
        train_size = x_d.shape[0] - nn_hyps['max_test_size'] - nn_hyps['n_lag_d']
      else:
        train_size = x_d.shape[0] - test_size - nn_hyps['n_lag_d']
      if nn_hyps.get('bootstrap_indices', None) != None: # If there are bootstrap indices set already
        pass 
      else:
        if nn_hyps['fix_bootstrap'] == True:
            print('DataProcesser: Bootstraps fixed')
            bootstrap_indices = get_bootstrap_indices(num_bootstrap = nn_hyps['num_bootstrap'], n_obs = train_size, block_size = nn_hyps['block_size'], sampling_rate = nn_hyps['sampling_rate'], opt_bootstrap = nn_hyps['opt_bootstrap'])
            nn_hyps['bootstrap_indices'] = bootstrap_indices
        else:
            nn_hyps['bootstrap_indices'] = None

    if nn_hyps['same_train'] == True: # If same train - use the same train-test split (split at max_test_size), and cut down X_test to test_size
      X_train, X_test, Y_train, Y_test, x_mat_all, y_mat, nn_hyps = process_data(x_d, nn_hyps, test_size = max_test_size, n_time_trends = 100,
        time_dummy_setting = nn_hyps['time_dummy_setting'], marx = nn_hyps['marx'], dummy_interval = nn_hyps['dummy_interval'])
      
      X_test = X_test[(-test_size):, :]
      Y_test = Y_test[(-test_size):, :]
      print(f'Cut down X_test and Y_test by {max_test_size - test_size}')
    
    else:
      X_train, X_test, Y_train, Y_test, x_mat_all, y_mat, nn_hyps = process_data(x_d, nn_hyps, test_size = test_size, n_time_trends = 100,
        time_dummy_setting = nn_hyps['time_dummy_setting'], marx = nn_hyps['marx'], dummy_interval = nn_hyps['dummy_interval'])

    n_inputs_total = X_train.shape[1]

    n_endog_inputs = n_var * (nn_hyps['n_lag_linear'] + nn_hyps['n_lag_d'])
    n_exog_inputs = 0 if nn_hyps['exog'] is None else nn_hyps['exog'].shape[1]
    n_time_inputs = n_inputs_total - n_endog_inputs - n_exog_inputs

    print(f'Endog: {n_endog_inputs}, Exog: {n_exog_inputs}, Time: {n_time_inputs}')

    # If s_pos is already not defined (s_pos can be defined by user)
    if nn_hyps.get('s_pos') is not None:
      if nn_hyps['s_pos_setting']['hemis'] == 'combined': # Endog + Time
        nn_hyps['s_pos'] = [ list(range(n_inputs_total)) ]
      elif nn_hyps['s_pos_setting']['hemis'] == 'endog':
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs)) ]
      elif nn_hyps['s_pos_setting']['hemis'] == 'exog': # Exogenous variables only
        n_inputs_total_new = n_endog_inputs + n_exog_inputs
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs, n_inputs_total_new)) ]
      elif nn_hyps['s_pos_setting']['hemis'] == 'time': # Time variables only
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs + n_exog_inputs, n_inputs_total)) ]
      elif nn_hyps['s_pos_setting']['hemis'] == 'endog_time': # now, we need to check n_time
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs)), list(range(n_endog_inputs + n_exog_inputs, n_inputs_total))]
      elif nn_hyps['s_pos_setting']['hemis'] == 'endog_exog': 
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs)), list(range(n_endog_inputs, n_endog_inputs + n_exog_inputs))]
      elif nn_hyps['s_pos_setting']['hemis'] == 'endog_exog_time':
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs)), list(range(n_endog_inputs, n_endog_inputs + n_exog_inputs)), list(range(n_endog_inputs + n_exog_inputs, n_inputs_total))]
      # For testing: 2 repeated endog hemispheres
      elif nn_hyps['s_pos_setting']['hemis'] == 'endog_endog': 
        nn_hyps['s_pos'] = [ list(range(n_endog_inputs)), list(range(n_endog_inputs))]

    else: # Format s_pos properly
      s_pos = nn_hyps['s_pos']
      nn_hyps['s_pos'] = [list(range(s[0], s[1])) for s in s_pos]

    print('s_pos', nn_hyps['s_pos'])

    # Get the max of s_pos
    max_s_pos = max([max(e) for e in nn_hyps['s_pos']])
    # Subset the X_train and X_test to only the required columns
    X_train = X_train[:, :(max_s_pos+1)]
    X_test = X_test[:, :(max_s_pos+1)]

    
    return X_train, X_test, Y_train, Y_test, nn_hyps



