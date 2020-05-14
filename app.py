import os

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.express as px

import pandas as pd
import numpy as np
import math
import json
from datetime import timedelta
from urllib.request import urlopen
from pandas.io.json import json_normalize



external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets = external_stylesheets)
#server = app.server



# read in test numbers
response = urlopen('https://api.covid19india.org/state_test_data.json')
testing = response.read()
data = json.loads(testing)
testing_df = pd.json_normalize(data['states_tested_data'])

# update column name and keep only four columns
testing_df.rename(columns = {'updatedon': 'date', 
                             'totaltested': 'tested', 
                             'positive': 'confirmed'}, 
                  inplace = True)
testing_df = testing_df.loc[:,['state', 'date', 'tested', 'confirmed']]

# drop rows without data, duplicates
testing_df['tested'].replace('', np.nan, inplace = True)
testing_df['confirmed'].replace('', np.nan, inplace = True)
testing_df.dropna(subset = ['tested', 'confirmed'], how = 'any', inplace = True)
testing_df.drop_duplicates(subset = ['state', 'date'], keep = "first", inplace = True)

# change data types
testing_df['date'] = pd.to_datetime(testing_df['date'], format = '%d/%m/%Y')
testing_df['tested'] = testing_df['tested'].astype(int)
testing_df['confirmed'] = testing_df['confirmed'].astype(int)

testing_df = testing_df[(testing_df['date'] > np.datetime64('2020-04-09'))]




# remove states with under 500 cases
all_states = testing_df.state.unique().tolist()
filtered_states = []

for state in all_states:
    state_df = testing_df[testing_df['state'] == state]
    latest_date = max(state_df.date)
    if state_df.loc[state_df['date'] == latest_date, 'confirmed'].values[0] >= 500:
        filtered_states.append(state)

testing_df = testing_df[testing_df.state.isin(filtered_states)]



# fill in data where unavailable
pd.set_option('mode.chained_assignment', None) 

all_states = testing_df.state.unique().tolist()
state_df_list = []

# for date index
latest_date = min(max(testing_df.date), np.datetime64('today'))
earliest_date = min(testing_df.date)
idx = pd.date_range(earliest_date, latest_date)

# loop through each state
for state in all_states:
    
    state_df = testing_df[testing_df['state'] == state]
    
    state_df.set_index(['date'], inplace = True)
    state_df = state_df.reindex(idx)
    
    # fill up data in all columns where NaN
    state_df['state'] = state
    state_df.fillna(method = 'ffill', inplace = True)
    state_df.fillna(method = 'bfill', inplace = True)
    
    # back to original format
    state_df.reset_index(inplace = True)
    state_df.rename(columns = {'index': 'date'}, inplace = True)
    state_df = state_df[['state', 'date', 'tested', 'confirmed']]
        
    state_df_list.append(state_df)
            
testing_df = pd.concat(state_df_list, axis = 0, sort = False, ignore_index = True)

pd.set_option('mode.chained_assignment', 'warn') 




# merge with auxiliary data
auxiliary_df = pd.read_csv("auxiliary.csv", index_col = False)
testing_df = pd.merge(left = testing_df, right = auxiliary_df, how = 'left', 
                             left_on = 'state', right_on = 'state')





# calculate important fields
testing_df['testPosRate'] = testing_df['confirmed'] / testing_df['tested'] * 100
testing_df['testPer1M'] = testing_df['tested'] / testing_df['population'] * 1000000
testing_df['date_string'] = testing_df['date'].dt.strftime('%Y/%m/%d')
maxPosRate = math.ceil(max(testing_df.testPosRate)) + 1
maxPer1M = int(math.ceil((max(testing_df.testPer1M) + 500) / 500.0)) * 500




fig = px.scatter(testing_df, 
                 x = "testPosRate", 
                 y = "testPer1M", 
                 animation_frame = "date_string", 
                 animation_group = "state",
                 size = "confirmed", 
                 color = "zone", 
                 opacity = 0.6,
                 text = "abbr",
                 width = 950,
                 height = 600,
                 range_x = [0, maxPosRate], 
                 range_y = [0, maxPer1M],
                 labels = {'zone': 'Zones',
                           'testPer1M': 'Tests Per Million',
                           'testPosRate': 'Test Positivity Rate(%)',
                           'date_string': 'Date',
                           'abbr': 'Abbreviation', 
                           'confirmed': 'Confirmed',
                           'tested': 'Tests Conducted'},
                 hover_name = "state",
                 hover_data = ['tested'],
                 template = "simple_white"
                )
fig.update_traces(textposition = 'top center')






app.layout = html.Div([ 
    # title
    html.H2('Statewise COVID-19 Testing in India', style = {'textAlign': 'center'}),
    
    # text above plot
    html.Div([
        html.P('Low Test Positivity Rate and High Tests Per Million are indicators of good testing efforts.', style = {'fontSize': '14px', 'fontWeight': 'bold', 'color': "#2ca02c"}
        )
    ], style = {'textAlign': 'center', 'paddingTop': '5px'}),
    html.Div([
        html.P('Bubble size represents number of confirmed cases.', style = {'fontSize': '14px'}
        )
    ], style = {'textAlign': 'right', 'paddingRight': '15%'}),
    
    # plot
    html.Div(
        dcc.Graph(figure = fig), style = {'display': 'flex', 'justifyContent': 'center'}
    ),
    
    # text below plot
    html.Div([
        'Indian Government is focusing on two major metrics as it works to contain the spread of COVID-19 in India: Test Positivity Rate and Tests Per Million.', html.Br(), 
        html.Span('Test Positivity Rate', style = {'fontWeight': 'bold'}),
        ' tells us what percentage of the samples tested came back be positive. A low value of test positivity rate is a good indicator that we are not undercounting the total number of COVID-19 patients too much.', html.Br(), 
        html.Span('Tests Per Million', style = {'fontWeight': 'bold'}),
        ' tells us what proportion of the population has been tested. Tests Per Million could be significantly skewed by the population of the state and thus might be a weaker metric than Test Positivity Rate.', html.Br(), 
        'The above graph shows how the different states are doing in their testing efforts.'
    ], style = {'textAlign': 'justified', 'paddingTop': '20px', 'paddingLeft': '15%', 'paddingRight': '15%'}),
    
    # source on right
    html.Div([
        html.P([
            'Testing data acquired from ', 
            html.A("https://api.covid19india.org", href = "https://api.covid19india.org")
        ], style = {'fontSize': '11px'})
    ], style = {'textAlign': 'right', 'paddingTop': '30px', 'paddingRight': '15%'})
])





if __name__ == '__main__':
#    app.run_server(debug=True)
    port = 8000 
    app.run_server(host='127.0.0.1', port = port)