from simulator import Manager
import time

start_time = time.time()
model = Manager('CCLine.xlsx')
model.run_simulation('ra',5,1000,'trace.txt')
print("--- %s seconds ---" % (time.time() - start_time))