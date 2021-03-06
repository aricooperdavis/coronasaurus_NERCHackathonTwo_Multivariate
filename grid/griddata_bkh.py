import pickle

import numpy as np
import pandas as pd

import bokeh.plotting as bkh
import bokeh.models as bkm

class GridData:
    def __init__(self, grid_file):
        self.grid = pd.read_csv(grid_file)
        self.grid['DATE'] = pd.to_datetime(self.grid['SETTLEMENT_DATE'], format='%d-%b-%Y')
        
        self.grid_average = self.grid.groupby('DATE').agg(DEMAND_AVERAGE=pd.NamedAgg('ND',aggfunc=np.mean)).reset_index()
        self.grid_average['YEAR'] = self.grid_average['DATE'].dt.year
        self.grid_average['DOY'] = self.grid_average['DATE'].dt.dayofyear
        
        # Prepare the modelling data
        OFFSET = 0
        X = []
        for year in np.unique(self.grid_average.YEAR.values):
            DOY = OFFSET + self.grid_average.DOY[self.grid_average.YEAR.values==year]
            X += [i for i in DOY]
            OFFSET += max(self.grid_average.DOY[self.grid_average.YEAR.values==year])

        # Get X in years from the beginning, instead of days and transpose.
        self.X = np.expand_dims(np.array(X)/365, axis=1)
        
        # Get Y in GW instead of MW and transpose.
        self.Y = np.expand_dims(self.grid_average.DEMAND_AVERAGE.values/1000, axis=1)
        
    def get_data(self):
        return self.grid
        
    def get_data_average(self):
        return self.grid_average
        
    def plot_demand_bkh(self, collapse=True, color='black', figsize=(600,300)):
        p = bkh.figure(x_axis_type='datetime', plot_width=figsize[0], plot_height=figsize[1])
        colors = ['darkgreen','darkkhaki','darkmagenta','darksalmon','darkred','gold']
        i = 0
        
        if collapse:
            for year in np.unique(self.grid_average.YEAR.values):
                p.line(self.grid_average.DOY[self.grid_average.YEAR.values==year],
                       self.grid_average.DEMAND_AVERAGE[self.grid_average.YEAR.values==year],
                       line_width=2, alpha=0.4+0.1*i, legend_label=str(year), color=colors[i])
                i += 1
                
            p.xaxis.axis_label = 'Day of the Year'
            
        else:
            p.line(self.grid_average.DATE, self.grid_average.DEMAND_AVERAGE, color=color)
            p.xaxis.axis_label = 'Year'
            
        p.yaxis.axis_label = 'Demand (MW)'
        
        #bkh.output_notebook()
        bkh.show(p)
        
        
    def load_model(self, model_file, forecast_limit=7):
        
        try:
            import GPy
        except ModuleNotFoundError:
            return
        
        # Set the datapoint cutoff index for lockdown.
        self.COVID_CUTOFF = 1881
        
        # Set the forecasting limit.
        self.forecast_limit = forecast_limit
        
        # Open a pickled model.
        with open(model_file, 'rb') as f:
            self.model = pickle.load(f)
        
        # Predict the model from 0 to the forecasting limit
        self.X_PREDICT = np.expand_dims(np.linspace(0, self.forecast_limit, 1000), axis=1)
        self.Y_PREDICT_mean, self.Y_PREDICT_conf = self.model.predict(self.X_PREDICT)
        
        # Get the datapoints after the lockdown.
        self.X_COVID = self.X[self.COVID_CUTOFF:]
        self.Y_COVID = self.Y[self.COVID_CUTOFF:]
        
        # Predict the datapoints after the lockdown.
        self.Y_COVID_PREDICT_mean, self.Y_COVID_PREDICT_conf = self.model.predict(self.X_COVID)
        
    def load_model_output(self, output_file):
        
        # Set the datapoint cutoff index for lockdown.
        self.COVID_CUTOFF = 1881
        self.forecast_limit = 7
        
        # Open a pickled model.
        with open(output_file, 'rb') as f:
            self.output_dict = pickle.load(f)
        
        # Predict the model from 0 to the forecasting limit
        self.X_PREDICT = self.output_dict['X_PREDICT']
        self.Y_PREDICT_mean, self.Y_PREDICT_conf = self.output_dict['Y_PREDICT_mean'], self.output_dict['Y_PREDICT_conf']
        
        # Get the datapoints after the lockdown.
        self.X_COVID = self.output_dict['X_COVID']
        self.Y_COVID = self.output_dict['Y_COVID']
        
        # Predict the datapoints after the lockdown.
        self.Y_COVID_PREDICT_mean, self.Y_COVID_PREDICT_conf = self.output_dict['Y_COVID_PREDICT_mean'], self.output_dict['Y_COVID_PREDICT_conf']
        
    def plot_model_bkh(self, figsize=(600,300)):
        
        p = bkh.figure(plot_width=figsize[0], plot_height=figsize[1])
        
        p.varea(x=self.X_PREDICT.flatten()+2015,
                y1=(self.Y_PREDICT_mean-self.Y_PREDICT_conf).flatten(),
                y2=(self.Y_PREDICT_mean+self.Y_PREDICT_conf).flatten(),
                alpha=0.2, legend_label='Confidence')
        
        p.line(self.X_PREDICT.flatten()+2015, self.Y_PREDICT_mean.flatten(), legend_label='Mean')
        
        p.x(self.X[:self.COVID_CUTOFF].flatten()+2015, self.Y[:self.COVID_CUTOFF].flatten(), color='black', alpha=0.5, legend_label='Before Lockdown')
        
        p.x(self.X[self.COVID_CUTOFF:].flatten()+2015, self.Y[self.COVID_CUTOFF:].flatten(), color='red', alpha=0.5, legend_label='After Lockdown')
        
        p.xaxis.axis_label = 'Year'
        p.yaxis.axis_label = 'Net Demand (GW)'
        
        #bkh.output_notebook()
        bkh.show(p)
        
    def plot_demand_discrepancy_bkh(self, figsize=(600,300), plot_confidence=True):
        
        p = bkh.figure(plot_width=figsize[0], plot_height=figsize[1], x_axis_type='datetime')

        if plot_confidence:
            p.varea(x=self.grid_average.DATE[self.COVID_CUTOFF:], y1=(self.Y_COVID.flatten()/(self.Y_COVID_PREDICT_mean.flatten()+self.Y_COVID_PREDICT_conf.flatten())).flatten(),
                    y2=(self.Y_COVID.flatten()/(self.Y_COVID_PREDICT_mean.flatten()-self.Y_COVID_PREDICT_conf.flatten())).flatten(), alpha=0.2, legend_label='Confidence')
        
        p.line(x=self.grid_average.DATE[self.COVID_CUTOFF:], y=np.ones(len(self.grid_average.DATE[self.COVID_CUTOFF:])), line_dash='dashed', color='black')
        p.line(x=self.grid_average.DATE[self.COVID_CUTOFF:], y=self.Y_COVID.flatten()/self.Y_COVID_PREDICT_mean.flatten(), legend_label='Mean')

        p.xaxis.axis_label = 'Date'
        p.xaxis[0].formatter = bkm.DatetimeTickFormatter(days=['%d/%m'])
        
        p.yaxis.axis_label = 'Net Demand (True) / Net Demand (Expected)'

        #bkh.output_notebook()
        bkh.show(p)
