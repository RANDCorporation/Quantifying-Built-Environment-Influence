#################################################################################################
# 1. Import libraries and set up output folders
#################################################################################################
# Import Python libraries
import numpy as np  
import pandas as pd  
import networkx as nx 
import random as rng 
import os
import sys
import geopy.distance as gp
import logging as lg
from plotnine import *
from scipy import stats
# import ggplot

import multiprocessing as mp
from multiprocessing import Pool

pd.set_option('display.max_columns', 40)

#################################################################################################
# 1. Initialize Parameters
#################################################################################################
#Determine if the machine is running locally on Windows or remotely
#on linux (in which case, read in arguments passed from bash)


save       = True
plots      = True
smoothing  = False
pctdiff    = False

path = ''
city_sfx = "la"

# Set directory
os.chdir(path)

def percentile(n):
    def percentile_(x):
        return np.percentile(x, n)
    percentile_.__name__ = 'percentile_%s' % n
    return percentile_


# Detroit
det_features_list = ['Bank', 'Child Care Center', 'Credit union', 'Fedex', 'Fire Stations', 'Hospitals', 'Landfill', 'Law Enforcement', 
'LiqLics', 'Nursing Home', 'Pharmacy', 'Public health departments', 'RecCent', 'Schools', 'Slaughterhouses', 
'Sport Venue', 'State government', 'Transit station', 'University/College', 'UPS', 'Urgent care', 'VA', 'WIC']

# New Orleans
nola_features_list = ['Alcohol outlet', 'Bank', 'Credit union', 'Drug stores', 'Fedex', 'Fire Stations', 'Gas stations', 'Grocery Stores', 
'Hospital', 'Law Enforcement', 'Lodging', 'Nursing home', 'Pharmacy', 'Public health departments', 'Public library', 'Refrigerated warehouse', 
'Restaurants', 'School', 'Slaughterhouses', 'Sport Venue', 'Transit station', 'University/College', 'UPS', 'Urgent care', 'VA']
# nola_features_list.reverse()

# Pittsburgh
pgh_features_list = ['Bank', 'Child Care Center', 'Convenience Store', 'Convenience store or supermarket', 'Credit union', 'Fast Food', 
'Fedex', 'Fire Stations', 'Hospital', 'Landfill', 'Law Enforcement', 'Library', 'Mobile Home Parks', 'Nursing Home', 'Pharmacy', 
'Playground', 'Primary care providers', 'Private school', 'Public Buildings', 'Public health departments', 'Public park', 'Public pool', 
'Public school', 'Refrigerated warehouse', 'Slaughterhouses', 'Sport court', 'Sport field', 'Sport Venue', 'State government', 
'Tobacco retailer', 'Trade school', 'Transit station', 'University/College', 'UPS', 'Urgent care', 'VA']
# pgh_features_list.reverse()

# Los Angeles
la_features_list = ['Credit union', 'Fedex', 'Fire Stations', 'Hospital', 'Landfill', 'Law Enforcement', 'Mobile Home Parks', 'Museums', 'Nursing Home', 'Public health departments', 
'Slaughterhouses', 'Spectator sports', 'Sport Venue', 'State government', 'Trade school', 'Transit station', 'University/College', 'Urgent care', 'VA']
# la_features_list.reverse()

feature_type_df = pd.DataFrame(columns=['feature_name', 'distance', 'FeatureType'])

# for loop
if city_sfx=="la":
  rel_list = la_features_list
elif city_sfx=="pgh":
  rel_list = pgh_features_list
elif city_sfx == "nola":
  rel_list = nola_features_list
else:
  rel_list = det_features_list

for i in range(0,len(rel_list)):
    features = rel_list[i]
    print(features)

    features_nym = features

    if features == "University/College":
        features_nym = "UniCollege"

    #%%
    cross_k_sim_hold = pd.read_csv(city_sfx + '_' + str(features_nym) + '_' + str(1) + "_cross_k_simulated_results.csv")

    if city_sfx == "la":
      end = 201
    else:
      end = 41
    for x in range(2, end):
        df =  pd.read_csv(city_sfx + '_' + str(features_nym) + '_' + str(x) + "_cross_k_simulated_results.csv")
        cross_k_sim_hold = cross_k_sim_hold.append(df)

    cross_k_sim_results = cross_k_sim_hold

    #Transform the cross-k results into a pivoted dataset #For use graphing cross-k results against observed cross-k
    #The line of code below is very dense but briefly: #We take the cross-k results, group those results by distance and feature
    cross_k_simulated = cross_k_sim_results.set_index(["distance", "feature_name"]).groupby(["distance", "feature_name"])["cross_k"].agg(
                                                                                            ["min", "max","mean", "median", percentile(2.5), percentile(97.5)]).rename(columns = {
                                                                                             'min':'cross_k_min',
                                                                                             'max' : 'cross_k_max',
                                                                                             'mean' :'cross_k_mean',
                                                                                             'median' : 'cross_k_median',
                                                                                             'percentile_2.5' : 'cross_k_lower' ,
                                                                                             'percentile_97.5': 'cross_k_upper'}).reset_index()

    #%%
    cross_k_observed = pd.read_csv(city_sfx + "_cross_k_observed.csv")
    cross_k_compiled = cross_k_observed.merge(cross_k_simulated, how = 'inner', on = ["feature_name", "distance"])

    conditions = [(cross_k_compiled['cross_k_observed'] >= cross_k_compiled['cross_k_max']) ,
                  (cross_k_compiled['cross_k_observed'] > cross_k_compiled['cross_k_min']) & ((cross_k_compiled['cross_k_observed'] < cross_k_compiled['cross_k_max'])),
                  (cross_k_compiled['cross_k_observed'] <= cross_k_compiled['cross_k_min']) ]

    # Get Percentage Difference
    cross_k_compiled['pct difference'] = (cross_k_compiled[ 'cross_k_observed']-cross_k_compiled['cross_k_mean'])/(cross_k_compiled[ 'cross_k_observed'])

    # print(cross_k_compiled.head(50))
    # Get Feature Types
    choices = ['Attractor', 'Neutral', 'Repellant']

    cross_k_compiled['FeatureType'] = np.select(conditions, choices, default= 'NA')

    cross_k_compiled['feature'] = features

    if features == "Fedex" :
      cross_k_compiled['feature'] = 'Shipping Company 1'
    if features == "UPS" :
      cross_k_compiled['feature'] = 'Shipping Company 2'


    cross_k_compiled['feature_category'] = 0
    cross_k_compiled.loc[cross_k_compiled['FeatureType'] == "Attractor", 'feature_category'] = 100
    cross_k_compiled.loc[cross_k_compiled['FeatureType'] == "Repellant", 'feature_category'] = -100

    # Optional smoothing. If feature category is directly bookended by the same category, e.g., repellant (100), neutral (105), repellant (110)

    cross_k_smoothed = cross_k_compiled.copy()

    cross_k_smoothed['FeatureType'] = np.where((cross_k_smoothed['FeatureType'].shift(+1) == cross_k_smoothed['FeatureType'].shift(-1)) & 
                                          (cross_k_smoothed['FeatureType'] != cross_k_smoothed['FeatureType'].shift(-1)),
                                  cross_k_smoothed['FeatureType'].shift(-1), cross_k_smoothed['FeatureType'])

    cross_k_smoothed['feature_category'] = 0
    cross_k_smoothed.loc[cross_k_smoothed['FeatureType'] == "Attractor", 'feature_category'] = 100
    cross_k_smoothed.loc[cross_k_smoothed['FeatureType'] == "Repellant", 'feature_category'] = -100

    
    if smoothing :
      feature_type_df = feature_type_df.append(cross_k_smoothed[['feature_name', 'distance', 'FeatureType', 'feature', 'feature_category', 'pct difference']])
    else:
      feature_type_df = feature_type_df.append(cross_k_compiled[['feature_name', 'distance', 'FeatureType', 'feature', 'feature_category', 'pct difference']])

levels = list()

if smoothing: 
  # plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='feature', fill='FeatureType')) + theme_grey() + geom_tile()  + theme(axis_text_x = element_text(rotation=90, hjust=1)) + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900]) + scale_fill_manual(values=["#FDE725FF",  "#1F968BFF", "#440154FF"])
  plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='feature', fill='FeatureType')) + theme_grey() + geom_tile() + coord_trans(y='reverse') + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900]) + scale_fill_manual(values=[ "#9E9E9E", "#212121", "#F0F0F0"])
  plot.save(filename = '' + city_sfx + '_viz_smoothed.png')

else:
  # plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='feature', fill='FeatureType')) + theme_grey() + geom_tile() + theme(axis_text_x = element_text(rotation=90, hjust=1)) + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900]) + scale_fill_manual(values=["#FDE725FF",  "#1F968BFF", "#440154FF"])
  plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='feature', fill='FeatureType')) + theme_grey() + geom_tile() + coord_trans(y='reverse') + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900])  + scale_fill_manual(values=[ "#9E9E9E", "#212121", "#F0F0F0"])
  plot.save(filename = '' + city_sfx + '_viz.png')

  # plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='feature', fill='FeatureType')) + theme_grey() + geom_tile() + coord_trans(y='reverse') + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900])  + scale_fill_manual(values=[ "#9E9E9E", "#212121", "#F0F0F0"])
  # plot.save(filename = '' + city_sfx + '_viztestreverse.png')

plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='feature', fill='pct difference')) + geom_tile() + coord_trans(y='reverse') + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900]) + scale_fill_distiller(type= 'div', palette='Spectral', 
                                                                                                                                                                                                                    breaks=[-30, -20, -15, -10,-5,0]
                                                                                                                                                                                                                    # , labels=[-30, -20, -10,-5, 0]
                                                                                                                                                                                                                    ) 
# breaks=[0] ,
# + scale_colour_gradient(midpoint=0, low='lightgrey', high= 'black') 

# ValueError: Invalid color map name 'Greys' for type 'Diverging'.
# Valid names are: ['BrBG', 'PRGn', 'PiYG', 'PuOr', 'RdBu', 'RdGy', 'RdYlBu', 'RdYlGn', 'Spectral']
# + coord_trans(y='reverse')
# plot = ggplot(data=feature_type_df, mapping=aes(x='distance', y='rows', fill='pct difference')) + geom_tile() + theme(axis_text_x = element_text(rotation=90, hjust=1)) + scale_x_discrete(breaks=[0, 100, 200, 300, 400, 500, 600, 700, 800, 900]) + scale_fill_gradientn(colors= ,limits=[-10000, 10000], na_value ='grey50')
plot.save(filename = '' + city_sfx + '_degreeviz.png')

# wow = feature_type_df[feature_type_df.feature_name=="Refrigerated warehouse"]
# feature_type_df.replace([np.inf, -np.inf], np.nan)
# feature_type_df = feature_type_df.dropna()
# new = feature_type_df[feature_type_df["pct difference"] > -inf]

# print(feature_type_df.head(50)) # norm.range <- (range(), range)

# SES is Standard Normal. What percentile of SES each feature is in
# Make a histogram of how many locations fall into bin of percentiles of SES

