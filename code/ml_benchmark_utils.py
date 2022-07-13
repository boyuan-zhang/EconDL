import numpy as np 
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from utils import scale_data, invert_scaling


def train_ml_model(X_train, X_test, Y_train, Y_test, nn_hyps, model = 'RF'):

  n_var = Y_train.shape[0]
  if nn_hyps['standardize'] == True:
    print('Standardizing')
    scale_output = scale_data(X_train, Y_train, X_test, Y_test)
    X_train = scale_output['X_train']
    X_test = scale_output['X_test']
    Y_train = scale_output['Y_train']
    Y_test = scale_output['Y_test']

  models = []

  # OOB predictions
  pred = np.zeros_like(Y_train)
  pred[:] = np.nan
  
  for var in range(n_var):
    # Train the model for each variable, and append the trained model
    y_train = Y_train[:, var]

    if model == 'RF':
      model_obj = RandomForestRegressor(max_depth = 5, random_state = 0, oob_score = True)
    elif model == 'XGBoost':
      model_obj = XGBRegressor(max_depth = 5, subsample = 0.75)
    model_obj.fit(X_train, y_train)
    models.append(model_obj)

    # Get the predictions (OOB for RF)
    if model == 'RF':
      pred[:, var] = model_obj.oob_prediction_
    elif model == 'XGBoost':
      pred[:, var] = model_obj.predict(X_train)

  # Unstandardize preds
  if nn_hyps['standardize'] == True:
    pred = invert_scaling(pred, scale_output['mu_y'], scale_output['sigma_y'])

  return {'trained_model': models,
          'scale_output': scale_output,
          'standardize': nn_hyps['standardize'],
          'pred_in': pred}