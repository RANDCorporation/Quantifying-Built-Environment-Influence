
# parallel 'python est_obs_parallel.py {1}'  ::: "la" "det" "pgh" "nola"
# parallel 'python est_obs_parallel_lasmall.py {1}'  ::: "la" 
# parallel 'python est_obs_parallel_test.py {1}'  ::: "det" "pgh" "nola" "la"

# parallel 'python est_obs_parallel.py "det" '  :::  1
# parallel 'python est_obs_parallel_ses.py "det" '  :::  1
# parallel 'python est_obs_parallel_ses.py "pgh" '  :::  1

# parallel 'python est_obs_parallel_detliqlics_none.py "det" ' ::: 1
# parallel 'python est_obs_parallel_detliqlics_ses.py "det" ' ::: 1

# parallel 'python est_obs_parallel_ses.py "nola" '  :::  1
# parallel 'python est_obs_parallel_ses.py "pgh" '  :::  1


# parallel 'python est_obs_parallel_latransit_ses.py "la" '  :::  1
# parallel 'python est_obs_parallel_laconvenience_ses.py "la" '  :::  1

parallel 'python est_obs_parallel_labig.py "la" '  :::  1