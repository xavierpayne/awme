#!flask/bin/python

from flask import Flask, jsonify, abort, request
import pickle
import ConfigParser, os.path
import logging, sys

import networkx as nx

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
        logger.debug('Security Group does not exist')
        abort(404)

    return jsonify({'security-group': security_group_metadata_by_region_dict.get(region_string).get(sg_id)})

@app.route('/awme/api/v1.0/regions', methods=['GET'])
def get_regions():
    return jsonify({'supported-regions': config_supported_regions})

#Alpha features

@app.route('/awme/api/v1.1/graphs/in-use-aws-pipeline.graphml', methods=['GET'])
def get_in_use_aws_pipeline_graph():
    return get_complete_aws_pipeline_graph(False)

@app.route('/awme/api/v1.1/graphs/complete-aws-pipeline.graphml', methods=['GET'])
def get_complete_aws_pipeline_graph(show_unused_resources=True):
    awsGraph=nx.DiGraph()
    awsGraph.name = 'AWS Pipeline'
    awsGraph.add_node('public-internet', {'Label': 'Public Internet', 'Node Type': 'public-internet', 'Size': 100})
    awsGraph.add_node('unused-security-groups', {'Label': 'Unused Security Groups', 'Node Type': 'logical-grouping', 'Size': 10})
    
    for region in security_group_metadata_by_region_dict:
        awsGraph.add_node(region, {'Label': region, 'Node Type': 'aws-region', 'Size': 90})

        for sg_instance in security_group_metadata_by_region_dict[region]:
            sg_total_host_instance_cost_per_hour = 0.0
            sg_total_host_instance_cost_per_quarter = 0.0
            sg_total_host_instance_cost_per_year = 0.0
            
            sg_node_count = len(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('hosts'))

            if (sg_node_count > 0 or show_unused_resources):
                sg_label = str(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('sg_name')) + ' (' + str(sg_node_count) + ')'
    
                if (len(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('hosts')) > 0):
                    sg_node = sg_instance
                    sg_parent_node = None
                else:
                    sg_parent_node = 'unused-security-groups'
                    
                awsGraph.add_node(sg_instance, {'Label': sg_label,
                                                'SG-ID': sg_instance,
                                                'Node Type': 'security-group',
                                                'Cost Per Hour': sg_total_host_instance_cost_per_hour,
                                                'Cost Per Quarter': sg_total_host_instance_cost_per_quarter,
                                                'Cost Per Year': sg_total_host_instance_cost_per_year
                                               })
            
                if (sg_parent_node != None):
                    awsGraph.add_edge(sg_parent_node, sg_instance, {'Label': 'is a',  'Line Color': '#999999'})
            
                if (security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags') != None and
                    len(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags')) > 0):
                    upstreamCommaSepTag = security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags').get('upstream_sg_ids')
    
                    if (upstreamCommaSepTag != None):
                        upstreamList = upstreamCommaSepTag.split(',')
    
                        for upstreamSG in upstreamList:
                            awsGraph.add_edge(upstreamSG, sg_instance, {'Label': 'upstream',  'Line Color': '#999999'} )
    
                for host_instance in security_group_metadata_by_region_dict.get(region).get(sg_instance).get('hosts'):
                    numTags = len(host_instance.get('tags'))
                    product_service = None
                    product = None
                    
                    if (numTags > 0):
                        product_service = host_instance.get('tags').get('Product Service')
                        product = host_instance.get('tags').get('Product')
                        
                    if (product_service == None):
                        product_service = 'No Details Provided. Ask DevOps/Engineering to provide more detail.'
    
                    if (product == None):
                        product = 'No Details Provided. Ask DevOps/Engineering to provide more detail.'
    
                    price_per_hour = float(config.get('aws_hourly_pricing', host_instance['instance_type']))
                    price_per_quarter = price_per_hour * 24.0 * 91.31
                    price_per_year = price_per_hour * 24.0 * 365.25
                    
                    sg_total_host_instance_cost_per_hour += price_per_hour
                    sg_total_host_instance_cost_per_quarter += price_per_quarter
                    sg_total_host_instance_cost_per_year += price_per_year
    
                    hostname = host_instance['public_dns_name']
                    if (hostname == ''):
                        hostname = 'No Hostname Assigned'
    
                    host_instance_size = int(price_per_year / 12.0)
    
                    awsGraph.add_node(host_instance['instance_id'],
                                       {'Label': hostname,
                                        'Host-ID': host_instance['instance_id'],
                                        'Node Type': 'host-instance',
                                        'Product': product,
                                        'Product Service': product_service,
                                        'Instance Type': host_instance['instance_type'],
                                        'Cost Per Hour': price_per_hour,
                                        'Cost Per Quarter': price_per_quarter,
                                        'Cost Per Year': price_per_year,
                                        'Size': host_instance_size
                                       })
                    
                    awsGraph.add_edge(host_instance['instance_id'], sg_instance, {'Label': 'member of',  'Line Color': '#999999'})

            if (sg_node_count > 0 or show_unused_resources):
                sg_total_host_instance_cost_per_hour += sg_total_host_instance_cost_per_hour
                sg_total_host_instance_cost_per_quarter += sg_total_host_instance_cost_per_quarter
                sg_total_host_instance_cost_per_year += sg_total_host_instance_cost_per_year
                
                awsGraph.node[sg_instance]['Cost Per Hour'] = sg_total_host_instance_cost_per_hour
                awsGraph.node[sg_instance]['Cost Per Quarter'] = sg_total_host_instance_cost_per_quarter
                awsGraph.node[sg_instance]['Cost Per Year'] = sg_total_host_instance_cost_per_year
                
                if (sg_total_host_instance_cost_per_year > 0):
                    sg_node_size = int(sg_total_host_instance_cost_per_year / 12.0)
                    awsGraph.node[sg_instance]['Size'] = sg_node_size
                else:
                    awsGraph.node[sg_instance]['Size'] = 5
    
    nx.write_graphml(awsGraph,"/tmp/test.graphml")

    return open("/tmp/test.graphml", "r").read()

    #return "hello!"
    
def getPricing(instanceType):
    return config.get('aws_hourly_pricing', instanceType)

@app.route('/awme/api/v1.1/graphs/show-aws-pipeline.png', methods=['GET'])
def get_aws_pipeline_graph_png():
    return "hello!"

def main():   
    #launch server
    app.run(host='0.0.0.0', port=10080, debug=True)

    #get_aws_pipeline_graph()


if __name__ == '__main__':
    main()