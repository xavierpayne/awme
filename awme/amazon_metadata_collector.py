#!/usr/bin/python

import boto.ec2, boto.ec2.elb, boto.rds
import pickle
import logging, sys
import ConfigParser, time, os.path, thread

class AmazonInstanceDataCollector(object):
    '''
    classdocs
    '''
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    #default our unbounded data structures to None. This ensures that 
    #initialize is called at least once.
    hosts_by_region_dict = None
    sg_by_region_dict = None
    elbs_by_region_dict = None
    rds_by_region_dict = None
   
    #Config variables are just defaults.
    #They can be replaced in the config.ini.
    config_supported_regions = list()   
    config_persistence_dir = "/dev/shm"
    config_ignore_security_groups = list()

    def __init__(self, params):
        '''
        Constructor
        '''
        self.initialize_cache()
    
        if not os.path.isfile('../config/config.ini'):
            self.logger.error("Unable to load config.ini file!")
            exit(1)
        else:
            self.logger.info("Found config.ini file.")
        
        #not supported until python 2.7
        #config = ConfigParser.RawConfigParser(allow_no_value=True)
        config = ConfigParser.RawConfigParser()
        config.read('../config/config.ini')
        
        self.config_supported_regions = config.get('awme_general', 'supported_regions').strip().split(',')
        self.config_ignore_security_groups = config.get('awme_general', 'ignore_security_groups').strip().split(',')
        self.config_persistence_dir = config.get('awme_general', 'persistence_dir')

        self.logger.debug("Supported Regions %s" % self.config_supported_regions)
        for region_string in self.config_supported_regions:
            self.sg_by_region_dict[region_string] = dict()
            self.hosts_by_region_dict[region_string] = dict()
            self.elbs_by_region_dict[region_string] = dict()
            self.rds_by_region_dict[region_string] = dict()


    def getInstanceDataforHostname(self, hostname):
        return self.host_metadata_by_hostname_dict[hostname]


    def getInstanceDataForHostsInSecurityGroup(self, groupname):
        return self.host_in_security_group_dict[groupname]


    def loadInstanceDataFromAWS(self, region_string):
        host_metadata_by_instance_id_dict = dict()
        
        self.logger.debug("Fetching AWS instance metadata for region [%s]..." % region_string)
        ec2_conn = boto.ec2.connect_to_region(region_string)
        
        security_groups_dict = self.build_initial_security_groups_dict(ec2_conn)
        
        start_time = time.clock() 
        aws_reservations_list = ec2_conn.get_all_instances()

        self.logger.debug("Fetching AWS instance maintenance metadata...")
        aws_scheduled_maintenance_list = ec2_conn.get_all_instance_status(include_all_instances=True)
               
        tmp_host_maintenance_metadata_dict = dict()
               
        #turn list into a dictionary
        for instance in aws_scheduled_maintenance_list:
            tmp_host_maintenance_metadata_dict[instance.id] = instance
        
        response_time = time.clock() - start_time
            
        self.logger.debug("Response received in [%s] seconds!" % response_time)
        self.logger.debug("found [%s] reservations." % len(aws_reservations_list))
        self.logger.debug("-------------------------------------")
        self.logger.debug("Caching host metadata in memory...")

        for host_instance_list in aws_reservations_list:
            host_instance_dict = dict()
        
            for host_instance in host_instance_list.instances:
                host_instance_dict['vpc-id'] = host_instance.vpc_id
                host_instance_dict['instance_id'] = host_instance.id
                host_instance_dict['instance_type'] = host_instance.instance_type
                host_instance_dict['placement'] = host_instance.placement
                host_instance_dict['state'] = host_instance.state
                host_instance_dict['launch-time'] = host_instance.launch_time
                host_instance_dict['public_dns_name'] = host_instance.public_dns_name
                host_instance_dict['private_dns_name'] = host_instance.private_dns_name
                host_instance_dict['image-id'] = host_instance.image_id
                host_instance_dict['subnet-id'] = host_instance.subnet_id
                host_instance_dict['ip-address'] = host_instance.ip_address
                host_instance_dict['private-ip-address'] = host_instance.private_ip_address
                host_instance_dict['root-device-name'] = host_instance.root_device_name
                host_instance_dict['root-device-type'] = host_instance.root_device_type
                host_instance_dict['instance-profile'] = host_instance.instance_profile
                host_instance_dict['tags'] = host_instance.__dict__['tags']
                # this one will need to be translated because it does not pickle gracefully
                #host_instance_dict['block-device-mapping'] = host_instance.block_device_mapping
                
                #Make sure the host knows what security groups it belongs to
                sg_list = list()
                
                for sg_instance in host_instance.groups:
                    if (sg_instance.id in self.config_ignore_security_groups):
                        continue
                    
                    sg_dict = dict()
                    sg_dict['sg_id'] = sg_instance.id
                    sg_dict['sg_name'] = sg_instance.name
                    
                    sg_list.append(sg_dict)

                    #Maintain a reverse lookup that allows us to see what hosts are in a security group                    
                    security_groups_dict.get(sg_instance.id).get('hosts').append(host_instance_dict)

                host_instance_dict['security_groups'] = sg_list

                #Add information about any scheduled events
                if (tmp_host_maintenance_metadata_dict.has_key(host_instance.id) and
                    tmp_host_maintenance_metadata_dict.get(host_instance.id).events != None):
                    self.logger.debug("instance [%s] has scheduled events!!!" % tmp_host_maintenance_metadata_dict[host_instance.id])
                    self.logger.debug("  event description: [%s] " % tmp_host_maintenance_metadata_dict.get(host_instance.id).events)
                    
                    #host_instance_dict['scheduled-events'] = tmp_host_maintenance_metadata_dict.get(host_instance.id)

                host_metadata_by_instance_id_dict[host_instance.id] = host_instance_dict
        
        self.hosts_by_region_dict[region_string] = host_metadata_by_instance_id_dict
        self.sg_by_region_dict[region_string] = security_groups_dict
        
        self.logger.debug("In memory data refreshed from AWS for region [%s]!" % region_string)

    def getAllInstanceStatus(self, region_string):
        self.logger.debug("Fetching AWS Instance Status metadata for region [%s]..." % region_string)
        ec2_conn = boto.ec2.connect_to_region(region_string)
        
        return ec2_conn.get_all_instance_status(include_all_instances=True)

    def loadRDSDataFromAWS(self, region_string):
        self.logger.debug("Fetching AWS Relational Database Service metadata for region [%s]..." % region_string)
        rds_conn = boto.rds.connect_to_region(region_string)
        rds_instances = rds_conn.get_all_dbinstances()
        rds_conn.get_all_dbsecurity_groups
        
        self.logger.debug("Found [" + str(len(rds_instances)) + "] Relational Database Services.")

        rds_metadata_by_name_dict = dict()
        
        for rds_instance in rds_instances:
            self.logger.debug("Found RDS name[" + str(rds_instance.id) + "] in security groups " + str(rds_instance.security_groups))
            rds_metadata_by_name_dict['name'] = rds_instance.id
            rds_instance_dict = dict()
            rds_instance_dict['rds_id'] = rds_instance.id
            rds_instance_dict['security_groups'] = rds_instance.security_groups
            
            for sg_instance in rds_instance.security_groups:
                #Maintain a reverse lookup that allows us to see what hosts are in a security group                    
                self.sg_by_region_dict.get(region_string).get(sg_instance).get('relational_database_services').append(rds_instance_dict)

            #rds_metadata_by_name_dict['security-group'] = elb.name

        self.rds_by_region_dict[region_string] = rds_metadata_by_name_dict



    def loadELBDataFromAWS(self, region_string):
        self.logger.debug("Fetching AWS Elastic Load Balancer metadata for region [%s]..." % region_string)
        elb_conn = boto.ec2.elb.connect_to_region(region_string)
        balancers = elb_conn.get_all_load_balancers()

        self.logger.debug("Found [" + str(len(balancers)) + "] Load Balancers.")

        elb_metadata_by_name_dict = dict()

        for elb in balancers:
            self.logger.debug("Found ELB name[" + str(elb.name) + "] in security groups " + str(elb.security_groups))
            elb_metadata_by_name_dict['name'] = elb.name
            elb_instance_dict = dict()
            elb_instance_dict['name'] = elb.name
            elb_instance_dict['security_groups'] = elb.security_groups
            
            for sg_instance in elb.security_groups:
                #Maintain a reverse lookup that allows us to see what hosts are in a security group                    
                self.sg_by_region_dict.get(region_string).get(sg_instance).get('load_balancers').append(elb_instance_dict)

            #elb_metadata_by_name_dict['security-group'] = elb.name

        self.elbs_by_region_dict[region_string] = elb_metadata_by_name_dict


    def build_initial_security_groups_dict(self, ec2_conn):
        aws_security_group_list = ec2_conn.get_all_security_groups()
        security_groups_dict = dict()

        for security_group in aws_security_group_list:
            sg_dict = dict()
            sg_dict['sg_name'] = security_group.name
            sg_dict['hosts'] = list() #Hosts is empty just for initialization
            sg_dict['load_balancers'] = list() #Load Balancers is empty just for initialization
            sg_dict['relational_database_services'] = list() #RDS list is empty just for initialization
            sg_dict['tags'] = security_group.__dict__['tags']

            security_groups_dict[security_group.id] = sg_dict

        return security_groups_dict


    def cache_out(self):
        #Serialize our data structures to disk
        pickle.dump(self.hosts_by_region_dict, open("%s/host_metadata.pickle.tmp" % self.config_persistence_dir, "wb"))
        pickle.dump(self.sg_by_region_dict, open("%s/security_group_metadata.pickle.tmp" % self.config_persistence_dir, "wb"))
        pickle.dump(self.elbs_by_region_dict, open("%s/elb_metadata.pickle.tmp" % self.config_persistence_dir, "wb"))
        pickle.dump(self.rds_by_region_dict, open("%s/rds_metadata.pickle.tmp" % self.config_persistence_dir, "wb"))
        
        self.logger.debug("In memory data written to: [%s]!" % self.config_persistence_dir)


    def initialize_cache(self):
        self.hosts_by_region_dict = dict()
        self.sg_by_region_dict = dict()
        self.elbs_by_region_dict = dict()
        self.rds_by_region_dict = dict()


def pull_amazon_metadata():
    amazonInstanceDataCollector = AmazonInstanceDataCollector(None)
    
    #make sure we start with a clean slate.
    amazonInstanceDataCollector.initialize_cache()

    #fill the cache    
    for region_string in amazonInstanceDataCollector.config_supported_regions:
        amazonInstanceDataCollector.loadInstanceDataFromAWS(region_string)
        amazonInstanceDataCollector.loadELBDataFromAWS(region_string)
        
        #RDS code not yet ready for prime time.
        #amazonInstanceDataCollector.loadRDSDataFromAWS(region_string)

    #flush the cache to disk
    amazonInstanceDataCollector.cache_out()
    print("Done!")


if __name__ == "__main__":
    
    while True:
        pull_amazon_metadata()
        
        #wait 5 minutes before pulling again.
        time.sleep(300)