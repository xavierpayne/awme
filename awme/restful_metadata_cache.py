#!flask/bin/python

from flask import Flask, jsonify, abort, request
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


@app.route('/awme/api/v1.0/host_instances', methods=['GET'])
def get_all_host_instances():
    return jsonify({'host-instances': host_metadata_by_region_dict})


@app.route('/awme/api/v1.0/sg_instances', methods=['GET'])
def get_all_sg_instances():
    return jsonify({'security-groups': security_group_metadata_by_region_dict})

#http://localhost:10080/ops/api/v1.0/host_instances/i-80380bca?region=eu-west-1c
@app.route('/awme/api/v1.0/host_instances/<string:instance_id>', methods=['GET'])
def get_host_instance_by_id(instance_id):
    region_string = request.args.get('region')
    logger.debug('Got a request for host [%(1s)s] in region [%(2s)s]' % {'1s' : instance_id, '2s' : region_string})
    if (region_string not in host_metadata_by_region_dict):
        logger.debug('Region does not exist')
        abort(404)

    if (instance_id not in host_metadata_by_region_dict.get(region_string)):
        logger.debug('Host does not exist')
        abort(404)

    return jsonify({'host-instance': host_metadata_by_region_dict.get(region_string).get(instance_id)})


@app.route('/awme/api/v1.0/sg_instances/<string:sg_id>', methods=['GET'])
def get_sg_instance_by_id(sg_id):
    region_string = request.args.get('region')
    logger.debug('Got a request for security-group-id [%(1s)s] in region [%(2s)s]' % {'1s' : sg_id, '2s' : region_string})
    if (region_string not in security_group_metadata_by_region_dict):
        logger.debug('Region does not exist')
        abort(404)

    if (sg_id not in security_group_metadata_by_region_dict.get(region_string)):
        logger.debug('Host does not exist')
        abort(404)

    return jsonify({'security-group': security_group_metadata_by_region_dict.get(region_string).get(sg_id)})

@app.route('/awme/api/v1.0/regions', methods=['GET'])
def get_regions():
    return jsonify({'supported-regions': config_supported_regions})

def main():   
    #launch server
    app.run(host='0.0.0.0', port=10080, debug=True)

if __name__ == '__main__':
    main()