#! /usr/bin/env python

# Import Python libraries
import pandas as pd 
import networkx as nx  
import ruptures as rpt
import geopy.distance as gp
import os
import sys

#Plotting package, emulating ggplot
from plotnine import ggplot, aes, theme_classic, labs, stat_smooth, geom_point, save_as_pdf_pages, stat_summary
import statsmodels.formula.api as smf

#Import the logger, to aid with debugging
import logging as lg


#Set up initial options, parameters, and loggers
test  = False
plots = True
save  = True

print("Running now")

if test:
    features = ['Public health departments']

distancerange = 1000
buffer = 300

breakpoint_sensitivity = 7.5



# Set directory
if os.name == 'nt': 
    city_sfx = 'det'
    path = ''

    
else:
    city_sfx = sys.argv[1]
    # side = sys.argv[2]
    path = ''
    
os.chdir(path)

#Set up the logger settings
lg.basicConfig(filename = city_sfx + "_log_messages.log", 
               format = '%(asctime)s %(levelname)s: \n\r%(message)s\n',
               datefmt='%Y-%m-%d %H:%M:%S',
               level = lg.DEBUG,
               filemode = 'w')

lg.debug("All packages loaded & model parameters initialized")

print(city_sfx)


if test:
    lg.debug("Test == TRUE; Only running models for the following features: %s", features)

#%%

G = nx.DiGraph(nx.read_gpickle(city_sfx + '_network_graph_v5.gpickle'))
G = G.to_undirected()

lg.debug("Network graph for New Orleans read successfully" )

def convert_network_nodes_to_df (g):
    nx_attributes = list()
    n_nodes = list()
    #Build a dataframe holding all of the node attributes
    for n in g.nodes(data = False):
       #Try/except is necessary here because a large fraction of nodes are intersections without 
       #any attributes; conversely, if a node isn't in the nx_attributes dataset, that indicates it's purely an intersection
       try:
           node_attributes = g.nodes[n]
           nx_attributes.append(node_attributes)
           n_nodes.append(n)
       except KeyError:
           pass  
       
    n_n_df = pd.DataFrame(nx_attributes)
    n_n_df['NodeID'] = pd.Series(n_nodes)
    return n_n_df

network_nodes = convert_network_nodes_to_df(G)


lg.debug("Network node dataframes have been produced")

#For each feature & distance, calculate the number of shots within that distance,
#to a given feature 

lg.debug("Now estimating shot densities by feature")

t_sum = 0
#Transform all the weights in the network into feet, rather than meters.
for u, v, d in G.edges(data = True):
    d['weight'] = d['weight']*3.28084
    t_sum += d['weight']
    
#Get a list of all the features in the network. Note: This will be overriden, if "test == True"
feature_list = network_nodes[network_nodes['category'] != "Gunshot"].category.unique().tolist()
feature_list = [x for x in feature_list if x == x]
print(feature_list)

#%%
#Set up all our functions, needed to calculate cross-k & the piecewise regression

def distance_calculator (f_name, feature_node_id, shot_node_id, dist_range, buff):
    """Determines the network distance between a 
    feature observation and a shot observation."""

    feature       = network_nodes[network_nodes['NodeID'] == feature_node_id]
    feature_coord = (feature.y.values[0], feature.x.values[0])

    shot          = network_nodes[network_nodes['NodeID'] == shot_node_id]
    shot_coord    = (shot.y.values[0], shot.x.values[0])

    #First, make sure the geodesic distance is reasonably close to our maximum range.
    #We do this to ensure we're not running the axstar function for irrelevant distances.
    #This aids in speeding up the calculation time.

    if gp.geodesic(feature_coord, shot_coord).feet < dist_range + buff:
        dist_between = nx.astar_path_length(G, source = feature_node_id, target = shot_node_id, weight = 'weight')
    else:
        dist_between = "Outside buffered range"

    return {'feature_name':f_name, 'feature_id': feature_node_id, 'shot_id': shot_node_id, 'distance':dist_between}

def shot_counter (f_name, d, n_feature, dist_mat): 

    """Calculates the number of shots within a given distance from a feature"""

    dist_mat = dist_mat[dist_mat['distance'] != "Outside buffered range"]

    #Make sure not to double-count shots, by only counting the unique shot_ids
    shot_counts  = dist_mat[dist_mat['distance'] <= d].shot_id.unique().size
    shot_density = shot_counts/d
    shot_density = shot_density/n_feature

    return {'feature_name': f_name, 'distance': d, 'shot_counts':shot_counts, 'shot_density':shot_density}

def cross_k (f_name, f_ids, s_ids, dist, s_c_mat, network_size = G.size(weight='weight')):

    """I don't think this is the right equation. The "number of shots" in the numerator is the
    same value as the "number of unique shots" in the denominator.  Why would we include both?
    """

    shot_count = s_c_mat[s_c_mat['distance'] == dist].shot_counts.values[0]

    number_features = f_ids.size
    number_shots    = s_ids.size

    cross_k = (network_size * shot_count)/(number_features * number_shots)

    return {'feature_name': f_name, 'distance': dist, 'cross_k_observed': cross_k}

def piecewise_plot (f_name, s_c_mat, city_sfx=city_sfx, b_sen = breakpoint_sensitivity, save_estimates = True):

    """Calculate breakpoints for a piecewise regression, using a penalized
    change point algorithm. Then, plot the shot density results, along with 
    the OLS results from determined breakpoints"""

    s_c_mat = s_c_mat[['distance', 'shot_density']]

    #Arrays are required for the penalized change point algorithm; let's pull those
    #out of the reduced dataframe above.
    shot_density = s_c_mat.shot_density.values

    #Try to algorithmically detect the breakpoints for the piecewise regression
    penalized_change_point = rpt.Pelt(model = "rbf").fit(shot_density)
    breakpoints = penalized_change_point.predict(pen = b_sen)

    breakpoints_dist = [x * 5 for x in breakpoints]

    save_name = f_name
    title_name = f_name

    if f_name == "University/College":
        save_name = "UniCollege"
    if f_name == "LiqLics":
        title_name = "Liquor Licenses"


    with open("{}_piecewise_ols_summary_{}.txt".format(city_sfx, save_name), 'w') as fh:
            fh.write("The Breakpoints are as below: \n {}\n".format(breakpoints_dist))

    #Create the initial figure
    piecewise_plot = (ggplot(s_c_mat, aes(x = 'distance', y = 'shot_density')) 
                        + geom_point() 
                        + theme_classic()
                        + labs(x = "Distance from {}".format(title_name),
                               y = "Density of shots per foot",
                               title = "{}".format(title_name)))

    # Add on OLS results at the estimated breakpoints.  
    # Note that the shot density array identifies the breakpoint of the index. 
    # To identify the actual distance, we need to multiply by 5, since distance is incremented by 5
    for i in range(len(breakpoints)):

        #Create lower and upper breakpoints
        if i == 0:
            break_lower = 0
            break_upper = breakpoints[i]*5
        elif i != len(breakpoints):
            break_lower = breakpoints[i - 1]*5
            break_upper = breakpoints[i]*5
        else:
            break_lower = breakpoints[i - 1]*5
            break_upper = distancerange

        #Add the smoother within the breakpoint ranges to the initial figure
        piecewise_plot = (piecewise_plot +
                          stat_smooth(data = s_c_mat[(s_c_mat['distance'] >= break_lower) & (s_c_mat['distance'] <= break_upper)], 
                                      method = 'ols', se = True, level = 0.95, span = 1, color = 'blue', alpha = 0.7))


        if save_estimates:
            ols = smf.ols(formula = "shot_density ~ distance", data = s_c_mat[(s_c_mat['distance'] >= break_lower) & (s_c_mat['distance'] <= break_upper)]).fit()

            with open("{}_piecewise_ols_summary_{}.txt".format(city_sfx, save_name), 'a') as fh:
                fh.write("Model breakpoints at: {}, {} \n".format(break_lower, break_upper))
                fh.write("\n\n ")
                fh.write(ols.summary().as_text())
                fh.write("\n\n")



    return piecewise_plot

def cross_k_plot(f_name, c_k_mat):

    """For a given feature, plot the cross-k results by distance """

    plot = (ggplot(c_k_mat, aes(x = 'distance', y = 'cross_k_observed')) 
        + geom_point() 
        + theme_classic()
        + labs(x = "Distance from {}".format(f_name),
               y = "Cross-K value",
               title = "{}".format(f_name)))

    return plot
    
def shot_count_plot (f_name, shot_count_mat):

    """For a given feature, plot counts of shots within a given distance """

    plot = (ggplot(shot_count_mat, aes(x = 'distance', y = 'shot_counts')) 
            + geom_point() 
            + theme_classic()
            + labs(x = "Distance from {}".format(f_name),
                   y = "Number of shots within distance, per total N of feature",
                   title = "{}".format(f_name)))

    return plot

def estimate_cross_k_and_piecewise (feature_name):

    """Runs all of the earlier created functions (distance calculator, shot counter, 
    cross-k, piecewise), in the appropriate order."""

    lg.debug("Starting cross-k calculations & piecewise regressions for {}".format(feature_name))

    #Create list of feature node ids and shot ids
    feature_ids     = network_nodes.loc[network_nodes['category'] == feature_name, 'NodeID']
    shot_ids        = network_nodes.loc[network_nodes['category'] == 'Gunshot','NodeID']

    #Count instances of feature
    n_feature = len(feature_ids)
    print("The number of instances of this feature is")
    print(n_feature)

    #Using the lists of features and shots, calculate the distance between the two
    distance_matrix = pd.DataFrame([distance_calculator(feature_name, f, s, distancerange, buffer) for f in feature_ids for s in shot_ids])


    #Use the calculated distances to determine the number of shots within a given range
    shot_count_matrix = pd.DataFrame([shot_counter(feature_name, dist, n_feature, distance_matrix) for dist in range(5, distancerange + 5, 5)])
    # print("View the shot count matrix")
    # print(shot_count_matrix)

    #Calculate cross-k
    cross_k_matrix =  pd.DataFrame([cross_k(feature_name, feature_ids, shot_ids, dist, shot_count_matrix) for dist in range(5, distancerange + 5, 5)])

    #Plot some results
    shot_count_fig = shot_count_plot(feature_name, shot_count_matrix)
    cross_k_fig    = cross_k_plot(feature_name, cross_k_matrix)
    piecewise_fig  = piecewise_plot(feature_name, shot_count_matrix)

    lg.debug("Success! {} is now finished".format(feature_name))

    return [distance_matrix, shot_count_matrix, cross_k_matrix, shot_count_fig, cross_k_fig, piecewise_fig]

#%%
#Below, this is the meat of the action. This runs the "estimate_shot_density" function, which runs all the subsidiary functions.
results = [estimate_cross_k_and_piecewise(f) for f in feature_list]

collected_distance_matrices   = pd.concat([x[0] for x in results], axis = 0)
collected_shot_count_matrices = pd.concat([x[1] for x in results], axis = 0)
collected_cross_k_matrices    = pd.concat([x[2] for x in results], axis = 0)

lg.debug("All features finished for cross-k and piecewise regression. Results compiled successfully!")


save_as_pdf_pages([x[3] for x in results], filename = city_sfx + "_shot_counts.pdf", filepath = path)
save_as_pdf_pages([x[4] for x in results], filename = city_sfx + "_cross_k.pdf", filepath = path)
save_as_pdf_pages([x[5] for x in results], filename = city_sfx + "_piecewise.pdf", filepath = path)

collected_distance_matrices.to_csv(city_sfx + "_distances_observed.csv", index = False)
collected_shot_count_matrices.to_csv(city_sfx + "_shot_counts_observed.csv", index = False)
collected_cross_k_matrices.to_csv(city_sfx + "_cross_k_observed.csv", index = False)



# #Save the produced figures to single PDF documents
# if plots:
#     save_as_pdf_pages([x[3] for x in results], filename = city_sfx + "_shot_counts.pdf", filepath = path)
#     save_as_pdf_pages([x[4] for x in results], filename = city_sfx + "_cross_k.pdf", filepath = path)
#     save_as_pdf_pages([x[5] for x in results], filename = city_sfx + "_piecewise.pdf", filepath = path)

#     lg.debug("Plots have finished writing to disk.")

# if save:
#     collected_distance_matrices.to_csv(city_sfx + "_distances_observed.csv", index = False)
#     collected_shot_count_matrices.to_csv(city_sfx + "_shot_counts_observed.csv", index = False)
#     collected_cross_k_matrices.to_csv(city_sfx + "_cross_k_observed.csv", index = False)

#     lg.debug("All datasets have been saved.")

lg.debug("All finished!")
