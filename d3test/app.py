
from flask import Flask, request
from datetime import datetime

import pwd
import json
import MDSplus
import numpy as np

app = Flask(__name__)

def vmsToUnix(timestamp):
    VMS_TICKS_PER_SECOND = 10_000_000
    VMS_OFFSET = 3506716800
    return (float(timestamp) / VMS_TICKS_PER_SECOND) - VMS_OFFSET

def _jsonify(data):
    args = request.args
    
    indent = None
    if args.get("pretty", default=False, type=bool):
        indent = 2
    
    return json.dumps(data, indent=indent)
    
def _open_tree(tree_name, shot_number):
    return MDSplus.Tree(tree_name, int(shot_number), 'READONLY')

def _get_node_info(node, args):
    
    time_inserted = vmsToUnix(node.time_inserted)
    owner = pwd.getpwuid(node.owner_id)[0]
    
    data = {
        "tree": node.tree.tree,
        "shot": node.tree.shot,
        "node": node.path,
        "usage": str(node.usage),
        "dtype": str(node.dtype_str),
        "time_inserted": datetime.fromtimestamp(time_inserted).isoformat(),
        "time_inserted_unix": time_inserted,
        "owner": owner,
    }
    
    graphWidth = args.get('graphWidth', '')
    
    startTime = args.get('startTime', None)
    endTime = args.get('endTime', None)
    
    # resample = args.get('resample', '1')
    # if resample == '':
    #     resample = '1'
        
    # resampleTimeUnits = None
    
    # if resample.endswith(('h', 'm', 's', 'ms', 'us', 'ns')):
    #     if resample.endswith(('ms', 'ns', 'us')):
    #         resampleTimeUnits = resample[-2:]
    #         resample = float(resample[:-2])
    #     else:
    #         resampleTimeUnits = resample[-1:]
    #         resample = float(resample[:-1])
    # else:
    #     resample = int(resample)
    
    
    # TODO: if?
    data['expression'] = str(node.record)
    
    # TODO: if?
    if node.dtype_str == 'DTYPE_F': # TSTART
        data['data'] = float(node.data())
    if node.usage == 'SIGNAL' or node.dtype_str == 'DTYPE_SIGNAL': # IP
        node_data = node.data()
        node_dim = node.dim_of().data()
        
        if graphWidth != '':
            graphWidth = int(graphWidth)
            
            start = node_dim[0] if startTime is None else float(startTime)
            end = node_dim[-1] if endTime is None else float(endTime)
            duration = end - start
            
            print('Time Range is [{}, {}]'.format(start, end))
            
            delta = duration / graphWidth
            
            print('Delta is {:.3}s'.format(delta))
            
            new_data = np.empty(graphWidth, dtype=node_data.dtype)
            new_dim = np.empty(graphWidth, dtype=node_dim.dtype)
            
            start_index = 0
            for j in range(len(node_dim)):
                if node_dim[j] >= start:
                    start_index = j
                    break
    
            node_data = node_data[start_index:]
            node_dim = node_dim[start_index:]
            
            for i in range(graphWidth):
                cutoff = min(start + (i + 1) * delta, end)
                
                # Hack for empty slice
                new_data[i] = new_data[i - 1]
                new_dim[i] = new_dim[i - 1]
                
                for j in range(len(node_dim)):
                    if node_dim[j] >= cutoff:
                        if j > 0:
                            new_data[i] = np.mean(node_data[:j])
                            new_dim[i] = np.mean(node_dim[:j])
                            node_data = node_data[j:]
                            node_dim = node_dim[j:]
                        break
                    
            node_data = new_data
            node_dim = new_dim
        
        # if resampleTimeUnits is not None:
        #     # convert everything to seconds
        #     if resampleTimeUnits == 'h':
        #         resample *= 3600.0
        #     elif resampleTimeUnits == 'm':
        #         resample *= 60.0
        #     elif resampleTimeUnits == 's':
        #         pass
        #     elif resampleTimeUnits == 'ms':
        #         resample /= 1000.0
        #     elif resampleTimeUnits == 'us':
        #         resample /= 1000000.0
        #     elif resampleTimeUnits == 'ns':
        #         resample /= 1000000000.0
            
        #     start = node_dim[0]
        #     end = node_dim[-1]
        #     new_length = int((end - start) / resample)
        #     new_data = np.empty(new_length + 1, dtype=node_data.dtype)
        #     new_dim = np.empty(new_length + 1, dtype=node_dim.dtype)
                
        #     for i in range(new_length):
        #         cutoff = start + (i + 1) * resample
                
        #         for j in range(len(node_dim)):
        #             if node_dim[j] >= cutoff:
        #                 new_data[i] = np.mean(node_data[:j])
        #                 new_dim[i] = np.mean(node_dim[:j])
        #                 node_data = node_data[j:]
        #                 node_dim = node_dim[j:]
        #                 break
                    
        #     new_data[new_length] = np.mean(node_data)
        #     new_dim[new_length] = np.mean(node_dim)
                    
        #     node_data = new_data
        #     node_dim = new_dim
                
                
        # elif resample > 1:
        #     new_length = int(len(node_data) / resample)
        #     new_data = np.empty(new_length, dtype=node_data.dtype)
        #     new_dim = np.empty(new_length, dtype=node_dim.dtype)
            
        #     for i in range(new_length):
        #         start = i * resample
        #         end = min((i + 1) * resample, len(node_data))
        #         new_data[i] = np.mean(node_data[start:end])
        #         new_dim[i] = np.mean(node_dim[start:end])
                
        #     node_data = new_data
        #     node_dim = new_dim
        
        data['data'] = {
            'values': node_data.tolist(),
            'dimension': node_dim.tolist()
        }
    
    return data

@app.route("/")
def index():
    return 'Hello, world!'

@app.route("/tree/<tree>")
def get_tree(tree):
    return ''

@app.route("/tree/<tree_name>/shot/<shot_number>")
def get_shot(tree_name, shot_number):
    tree = _open_tree(tree_name, shot_number)
    return _jsonify(_get_node_info(tree.top))

@app.route("/tree/<tree_name>/shot/<shot_number>/node/<node>")
def get_node(tree_name, shot_number, node):
    args = request.args
    
    tree = _open_tree(tree_name, shot_number)
    node = tree.getNode('\\' + node.upper())
    
    response = app.make_response(_jsonify(_get_node_info(node, args)))
    response.headers.add('Content-Type', 'application/json')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
    
@app.route("/tree/<tree_name>/shot/<shot_number>/tag/<tag>")
def get_tag(tree_name, shot_number, tag):
    args = request.args
    
    tree = _open_tree(tree_name, shot_number)
    node = tree.getNode('\\' + tag.upper())
     
    response = app.make_response(_jsonify(_get_node_info(node, args)))
    response.headers.add('Content-Type', 'application/json')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response