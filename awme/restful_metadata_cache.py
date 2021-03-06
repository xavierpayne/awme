#!flask/bin/python

from flask import Flask, jsonify, abort, request
import pickle
import ConfigParser, os.path
import logging, sys, time

import networkx as nx
from datetime import date

app = Flask(__name__)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

#failsafe defaults
config_supported_regions = list()
config_persistence_dir = "/dev/shm"

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

host_metadata_by_region_dict = dict()
security_group_metadata_by_region_dict = dict()
elastic_load_balancer_metadata_by_region_dict = dict()
rds_metadata_by_region_dict = dict()
s3_bucket_metadata_list = list()

last_refresh_time = 0

@app.route('/')
def index():
    return "Hello, World!"

@app.route('/awme/api/v1.0/s3_buckets', methods=['GET'])
def get_all_s3_buckets():
    refresh()

    return jsonify({'s3-buckets': s3_bucket_metadata_list})

@app.route('/awme/api/v1.0/rds_instances', methods=['GET'])
def get_all_rds_instances():
    refresh()

    return jsonify({'rds-instances': rds_metadata_by_region_dict})

@app.route('/awme/api/v1.0/host_instances', methods=['GET'])
def get_all_host_instances():
    refresh()

    return jsonify({'host-instances': host_metadata_by_region_dict})


@app.route('/awme/api/v1.0/sg_instances', methods=['GET'])
def get_all_sg_instances():
    refresh()

    return jsonify({'security-groups': security_group_metadata_by_region_dict})

@app.route('/awme/api/v1.0/host_instances/<string:instance_id>', methods=['GET'])
def get_host_instance_by_id(instance_id):
    refresh()
    
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
    refresh()
    
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
    refresh()
    
    return jsonify({'supported-regions': config_supported_regions})

#Alpha features
@app.route('/awme/api/v1.0/sg_instances/unused', methods=['GET'])
def get_unused_security_groups():
    refresh()
    
    unused_security_groups_by_region = dict()
    
    for current_region in config_supported_regions:
        all_security_groups = security_group_metadata_by_region_dict.get(current_region)
        unused_groups = list()
                    
        for sg in all_security_groups:
            sg_node_count = len(security_group_metadata_by_region_dict.get(current_region).get(sg).get('hosts'))
            sg_node_count += len(security_group_metadata_by_region_dict.get(current_region).get(sg).get('load_balancers'))
            
            if (sg_node_count == 0):
                unused_groups.append(sg)

        unused_security_groups_by_region[current_region] = unused_groups
    
    return jsonify({'unused-security-groups': unused_security_groups_by_region})

@app.route('/awme/api/v1.1/graphs/in-use-aws-pipeline.graphml', methods=['GET'])
def get_in_use_aws_pipeline_graph():
    #Refresh not necessary since this overloads another method that already has it
    #refresh()
    return get_complete_aws_pipeline_graph(False)

@app.route('/awme/api/v1.1/graphs/complete-aws-pipeline.graphml', methods=['GET'])
def get_complete_aws_pipeline_graph(show_unused_resources=True):
    refresh()
    
    #TODO cache the graph. Tricky part is there are multiple versions of the graph
    awsGraph=nx.DiGraph()
    awsGraph.name = 'AWS Pipeline'
    awsGraph.add_node('public-internet', {'Label': 'Public Internet', 'Node Type': 'public-internet', 'Size': 100})

    if (show_unused_resources):
        awsGraph.add_node('unused-security-groups', {'Label': 'Unused Security Groups', 'Node Type': 'logical-grouping', 'Size': 10})

    #process S3 Buckets
    for s3_bucket in s3_bucket_metadata_list:
        awsGraph.add_node(s3_bucket,
            {'Label': s3_bucket,
             'Node Type': 's3-bucket',
            })

    for region in security_group_metadata_by_region_dict:
        awsGraph.add_node(region, {'Label': region, 'Node Type': 'aws-region', 'Size': 90})

        for sg_instance in security_group_metadata_by_region_dict[region]:
            sg_total_host_instance_cost_per_hour = 0.0
            sg_total_host_instance_cost_per_quarter = 0.0
            sg_total_host_instance_cost_per_year = 0.0

            sg_node_count = len(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('hosts'))
            sg_node_count += len(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('load_balancers'))

            if (sg_node_count > 0 or show_unused_resources):
                sg_label = str(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('sg_name')) + ' (' + str(sg_node_count) + ')'

                if (sg_node_count > 0):
                    sg_node = sg_instance
                    sg_parent_node = None
                else:
                    sg_parent_node = 'unused-security-groups'

                awsGraph.add_node(sg_instance, {'Label': sg_label,
                                                'SG-ID': sg_instance,
                                                'Region': region,
                                                'Node Type': 'security-group',
                                                'Cost Per Hour': sg_total_host_instance_cost_per_hour,
                                                'Cost Per Quarter': sg_total_host_instance_cost_per_quarter,
                                                'Cost Per Year': sg_total_host_instance_cost_per_year
                                               })

                if (sg_parent_node != None):
                    awsGraph.add_edge(sg_parent_node, sg_instance, {'Label': 'is a',  'Line Color': '#c0c0c0'})

                if (security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags') != None and
                    len(security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags')) > 0):
                    upstreamCommaSepTag = security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags').get('upstream_sg_ids')
                    uploadsToS3BucketCommaSepTag = security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags').get('uploads_to_s3_bucket')
                    downloadsFromS3BucketCommaSepTag = security_group_metadata_by_region_dict.get(region).get(sg_instance).get('tags').get('downloads_from_s3_bucket')

                    if (upstreamCommaSepTag != None):
                        upstreamList = upstreamCommaSepTag.split(',')

                        for upstreamSG in upstreamList:
                            awsGraph.add_edge(upstreamSG, sg_instance, {'Label': 'upstream',  'Line Color': '#c0c0c0'} )

                    if (uploadsToS3BucketCommaSepTag != None):
                        uploadsToS3BucketList = uploadsToS3BucketCommaSepTag.split(',')

                        for upS3Bucket in uploadsToS3BucketList:
                            awsGraph.add_edge(upS3Bucket, sg_instance, {'Label': 'uploads-to',  'Line Color': '#c0c0c0'} )

                    if (downloadsFromS3BucketCommaSepTag != None):
                        downloadsFromS3BucketList = downloadsFromS3BucketCommaSepTag.split(',')

                        for downS3Bucket in downloadsFromS3BucketList:
                            awsGraph.add_edge(downS3Bucket, sg_instance, {'Label': 'downloads-from',  'Line Color': '#c0c0c0'} )

                #process Elastic Load Balancers
                for elb_instance in security_group_metadata_by_region_dict.get(region).get(sg_instance).get('load_balancers'):
                    awsGraph.add_node(elb_instance['name'],
                                       {'Label': elb_instance['name'],
                                        'Region': region,
                                        'Node Type': 'load-balancer',
                                       })
                    awsGraph.add_edge(elb_instance['name'], sg_instance, {'Label': 'member of',  'Line Color': '#c0c0c0'})

                #process hosts
                for host_instance in security_group_metadata_by_region_dict.get(region).get(sg_instance).get('hosts'):
                    if (host_instance['state'] == 'stopped'):
                        #if we are trying to show the clean view skip processing this
                        #node entirely and don't add it to the graph at all!
                        if (show_unused_resources == False):
                            continue
                        
                        host_color = '#ff0000' #Red
                        host_instance_cost_per_hour = 0.0
                        host_instance_cost_per_quarter = 0.0
                        host_instance_cost_per_year = 0.0
                    else:
                        host_color = '#008000' #Green
                        
                        #Not charged for stopped instances. Still charged for disks used but the cost is negligible.
                        host_instance_cost_per_hour = float(config.get('aws_hourly_pricing', host_instance['instance_type']))
                        host_instance_cost_per_quarter = host_instance_cost_per_hour * 24.0 * 91.31
                        host_instance_cost_per_year = host_instance_cost_per_hour * 24.0 * 365.25
                        
                        awsGraph.node[sg_instance]['Cost Per Hour'] += host_instance_cost_per_hour
                        awsGraph.node[sg_instance]['Cost Per Quarter'] += host_instance_cost_per_quarter
                        awsGraph.node[sg_instance]['Cost Per Year'] += host_instance_cost_per_year
                    
                    numTags = len(host_instance.get('tags'))
                    product_service = None
                    product = None
                    stack = None
                    
                    if (numTags > 0):
                        product_service = host_instance.get('tags').get('Product Service')
                        product = host_instance.get('tags').get('Product')
                        stack = host_instance.get('tags').get('Stack')

                    if (product_service == None):
                        product_service = 'No Details Provided. Ask DevOps/Engineering to provide more detail.'
    
                    if (product == None):
                        product = 'No Details Provided. Ask DevOps/Engineering to provide more detail.'

                    if (stack == None):
                        stack = 'No Details Provided. Ask DevOps/Engineering to provide more detail.'

                    hostname = determineHostname(host_instance)


                    #Add 120 just in case it was zero. Wouldn't want to divide by zero.
                    host_instance_size = int(host_instance_cost_per_year+120 / 12.0)

                    awsGraph.add_node(host_instance['instance_id'],
                                       {'Label': hostname,
                                        'Host-ID': host_instance['instance_id'],
                                        'Region': region,
                                        'Node Type': 'host-instance',
                                        'Stack': stack,
                                        'Product': product,
                                        'Product Service': product_service,
                                        'Instance Type': host_instance['instance_type'],
                                        'Cost Per Hour': host_instance_cost_per_hour,
                                        'Cost Per Quarter': host_instance_cost_per_quarter,
                                        'Cost Per Year': host_instance_cost_per_year,
                                        'state': host_instance['state'],
                                        'Size': host_instance_size,
                                        'Color': host_color
                                       })

                    awsGraph.add_edge(host_instance['instance_id'], sg_instance, {'Label': 'member of',  'Line Color': '#c0c0c0'})

            if (sg_node_count > 0 or show_unused_resources):
                #Add 120 just in case it was zero. Cleaner than another if block just because we don't want to divide by zero.
                sg_node_size = int(sg_total_host_instance_cost_per_year+120 / 12.0)

                awsGraph.node[sg_instance]['Size'] = sg_node_size
    
    nx.write_graphml(awsGraph,"/tmp/test.graphml")

    return open("/tmp/test.graphml", "r").read()

@app.route('/awme/api/v1.1/range/create-range-from-sg/<string:sg_id>', methods=['GET'])
def create_range_from_sg(sg_id):
    refresh()
    
    region_string = request.args.get('region')
    logger.debug('Got a request for security-group-id [%(1s)s] in region [%(2s)s]' % {'1s' : sg_id, '2s' : region_string})
    if (region_string not in security_group_metadata_by_region_dict):
        logger.debug('Region does not exist')
        abort(404)
    else:
        logger.debug('Region exists')

    if (sg_id not in security_group_metadata_by_region_dict.get(region_string)):
        logger.debug('Security Group does not exist')
        abort(404)
    else:
        logger.debug('Security Group exists')

    range_file =  "NOTE\n"
    range_file += "    INCLUDE \"Rangefile generated by AwMe for instances in security group ["
    range_file += security_group_metadata_by_region_dict.get(region_string).get(sg_id).get('sg_name')
    range_file += "] on " + time.strftime("%d/%m/%Y %H:%M:%S") + "\"\n"
    range_file +=  "\n"
    range_file +=  "ALL\n"
    range_file += "    INCLUDE $NODES\n"
    range_file +=  "\n"
    range_file += "CLUSTER\n"
    range_file += "    INCLUDE $ALL\n"
    range_file +=  "\n"
    range_file += "NODES\n"

    for host_instance in security_group_metadata_by_region_dict.get(region_string).get(sg_id).get('hosts'):
        hostname = determineHostname(host_instance)

        range_file += "    INCLUDE " + hostname + "\n"

    logger.debug('Range file generated:')
    logger.debug('range_file')

    return range_file

def getPricing(instanceType):
    return config.get('aws_hourly_pricing', instanceType)

def determineHostname(host_instance):
    numTags = len(host_instance.get('tags'))
    hostname = None
    
    if (numTags > 0):
        hostname = host_instance.get('tags').get('Name')
        
    if (hostname == None):
        if (host_instance['public_dns_name'] != ''):
            hostname = host_instance['public_dns_name']
        elif (host_instance['private_dns_name'] != ''):
            hostname = host_instance['private_dns_name']
        else:
            hostname = 'No Hostname Assigned'
    
    return hostname

def refresh():
    logger.debug("Checking if it's time for a refresh...")
    time_Now = time.time()
    global last_refresh_time, host_metadata_by_region_dict, security_group_metadata_by_region_dict, elastic_load_balancer_metadata_by_region_dict, rds_metadata_by_region_dict, s3_bucket_metadata_list

    #only reload if we have never loaded before OR at least 2 minutes has elapsed
    if (time_Now == 0 or time_Now - last_refresh_time > 120):
        host_metadata_by_region_dict = pickle.load(open("%s/host_metadata.pickle.tmp" % config_persistence_dir, "rb"))
        security_group_metadata_by_region_dict = pickle.load(open("%s/security_group_metadata.pickle.tmp" % config_persistence_dir, "rb"))
        elastic_load_balancer_metadata_by_region_dict = pickle.load(open("%s/elb_metadata.pickle.tmp" % config_persistence_dir, "rb"))
        rds_metadata_by_region_dict = pickle.load(open("%s/rds_metadata.pickle.tmp" % config_persistence_dir, "rb"))
        s3_bucket_metadata_list = pickle.load(open("%s/s3_metadata.pickle.tmp" % config_persistence_dir, "rb"))

        logger.debug("Memory refreshed from files in: [%s]!" % config_persistence_dir)

        last_refresh_time = time_Now
    else:
        logger.debug("NOT time for a refresh...")

@app.route('/awme/api/v1.1/graphs/show-aws-pipeline.png', methods=['GET'])
def get_aws_pipeline_graph_png():
    return "hello!"

def main():
    #launch server
    app.run(host='0.0.0.0', port=18080, debug=False)

if __name__ == '__main__':
    main()
