#!flask/bin/python

from flask import Flask, jsonify, abort
import pickle
import ConfigParser, os.path
import logging

app = Flask(__name__)

logger = logging.getLogger(__name__)

host_metadata_by_instance_id_dict = pickle.load(open("/dev/shm/host_metadata_by_instance_id_dict.pickle.tmp", "rb"))
security_group_info_by_sg_id_dict = pickle.load(open("/dev/shm/security_groups_dict.pickle.tmp", "rb"))
supportedRegions = list()

@app.route('/')
def index():
    return "Hello, World!"


@app.route('/ops/api/v1.0/host_instances', methods=['GET'])
def get_all_host_instances():
    return jsonify({'host-instances': host_metadata_by_instance_id_dict})


@app.route('/ops/api/v1.0/sg_instances', methods=['GET'])
def get_all_sg_instances():
    return jsonify({'security-groups': security_group_info_by_sg_id_dict})


@app.route('/ops/api/v1.0/host_instances/<string:instance_id>', methods=['GET'])
def get_host_instance_by_id(instance_id):
    if (instance_id not in host_metadata_by_instance_id_dict):
        abort(404)

    return jsonify({'host-instance': host_metadata_by_instance_id_dict[instance_id]})


@app.route('/ops/api/v1.0/sg_instances/<string:sg_id>', methods=['GET'])
def get_sg_instance_by_id(sg_id):
    if (sg_id not in security_group_info_by_sg_id_dict):
        abort(404)

    return jsonify({'security-group': security_group_info_by_sg_id_dict[sg_id]})

@app.route('/ops/api/v1.0/regions', methods=['GET'])
def get_regions():
    return jsonify({'supported-regions': supportedRegions})

def main():
    app.run(host='0.0.0.0', port=10080, debug=True)
    
    if not os.path.isfile('config.ini'):
        logger.error("Unable to load config.ini file!")
        exit(1)
    else:
        print "Found config.ini file."
    
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.read('config.ini')
    
    supportedRegions = config.get('am_e_general', 'supported_regions').strip().split(',')
    
    print "done."
    
if __name__ == '__main__':
    main()