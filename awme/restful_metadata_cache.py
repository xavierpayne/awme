#!flask/bin/python

from flask import Flask, jsonify, abort
import pickle
import ConfigParser, os.path
import logging, sys

app = Flask(__name__)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

if not os.path.isfile('../config/config.ini'):
    logger.error("Unable to load config.ini file!")
    exit(1)
else:
    logger.debug("Found config.ini file.")

#not supported until python 2.7
#config = ConfigParser.RawConfigParser(allow_no_value=True)
config = ConfigParser.RawConfigParser()
config.read('../config/config.ini')

config_persistence_dir = config.get('awme_general', 'persistence_dir')
config_supported_regions = config.get('awme_general', 'supported_regions').strip().split(',')

host_metadata_by_region_dict = pickle.load(open("%s/host_metadata.pickle.tmp" % config_persistence_dir, "rb"))
security_group_metadata_by_region_dict = pickle.load(open("%s/security_group_metadata.pickle.tmp" % config_persistence_dir, "rb"))

logger.debug("Data loaded into memory from: [%s]!" % config_persistence_dir)
config_supported_regions = list()   
config_persistence_dir = "/dev/shm"

@app.route('/')
def index():
    return "Hello, World!"


@app.route('/ops/api/v1.0/host_instances', methods=['GET'])
def get_all_host_instances():
    return jsonify({'host-instances': host_metadata_by_region_dict})


@app.route('/ops/api/v1.0/sg_instances', methods=['GET'])
def get_all_sg_instances():
    return jsonify({'security-groups': security_group_metadata_by_region_dict})


@app.route('/ops/api/v1.0/host_instances/<string:instance_id>', methods=['GET'])
def get_host_instance_by_id(instance_id):
    if (instance_id not in host_metadata_by_region_dict):
        abort(404)

    return jsonify({'host-instance': host_metadata_by_region_dict[instance_id]})


@app.route('/ops/api/v1.0/sg_instances/<string:sg_id>', methods=['GET'])
def get_sg_instance_by_id(sg_id):
    if (sg_id not in security_group_metadata_by_region_dict):
        abort(404)

    return jsonify({'security-group': security_group_metadata_by_region_dict[sg_id]})

@app.route('/ops/api/v1.0/regions', methods=['GET'])
def get_regions():
    return jsonify({'supported-regions': config_supported_regions})

def main():   
    #launch server
    app.run(host='0.0.0.0', port=10080, debug=True)

if __name__ == '__main__':
    main()