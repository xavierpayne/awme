#!/usr/bin/python

import boto.ec2
import pickle
import logging, sys
import ConfigParser, time, os.path

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
    
    hosts_by_region_dict = dict()
    sg_by_region_dict = dict()
   
    #Config variables are just defaults.
    #They can be replaced in the config.ini.
    config_supported_regions = list()   
    config_persistence_dir = "/dev/shm"

    def __init__(self, params):
        '''
        Constructor
        '''
        
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
        self.config_persistence_dir = config.get('awme_general', 'persistence_dir')

        self.logger.debug("Supported Regions %s" % self.config_supported_regions)
        for region_string in self.config_supported_regions:
            self.sg_by_region_dict[region_string] = dict()
            self.hosts_by_region_dict[region_string] = dict()

    def getInstanceDataforHostname(self, hostname):
        return self.host_metadata_by_hostname_dict[hostname]

    def getInstanceDataForHostsInSecurityGroup(self, groupname):
        return self.host_in_security_group_dict[groupname]

    def loadInstanceDataFromAWS(self, region_string):
        host_metadata_by_instance_id_dict = dict()
        
        self.logger.debug("Fetching AWS metadata for region [%s]..." % region_string)
        ec2_conn = boto.ec2.connect_to_region(region_string)
        
        self.logger.debug(boto.ec2.regions())
        
        security_groups_dict = self.build_initial_security_groups_dict(ec2_conn)
        
        start_time = time.clock() 
        aws_reservations_list = ec2_conn.get_all_instances()
        response_time = time.clock() - start_time
            
        self.logger.debug("Response received in [%s] seconds!\n" % response_time)
        self.logger.debug("found [%s] reservations." % len(aws_reservations_list))
        self.logger.debug("-------------------------------------")
        self.logger.debug("Caching host metadata in memory...")

        for host_instance_list in aws_reservations_list:
            host_instance_dict = dict()
        
            for host_instance in host_instance_list.instances:
                host_instance_dict['public_dns_name'] = host_instance.public_dns_name
                host_instance_dict['private_dns_name'] = host_instance.private_dns_name
                host_instance_dict['instance_id'] = host_instance.id
                host_instance_dict['placement'] = host_instance.placement
                
                #Make sure the host knows what security groups it belongs to
                sg_list = list()
                
                for sg_instance in host_instance.groups:
                    sg_dict = dict()
                    sg_dict['sg_id'] = sg_instance.id
                    sg_dict['sg_name'] = sg_instance.name
                    
                    sg_list.append(sg_dict)

                    #Maintain a reverse lookup that allows us to see what hosts are in a security group                    
                    security_groups_dict.get(sg_instance.id).get('hosts').append(host_instance_dict)

                host_instance_dict['security_groups'] = sg_list

                host_metadata_by_instance_id_dict[host_instance.id] = host_instance_dict
        
        self.hosts_by_region_dict[region_string] = host_metadata_by_instance_id_dict
        self.sg_by_region_dict[region_string] = security_groups_dict
        
        #Serialize our data structures to disk
        pickle.dump(self.hosts_by_region_dict, open("%s/host_metadata_by_instance_id_dict.pickle.tmp" % self.config_persistence_dir, "wb"))
        pickle.dump(self.sg_by_region_dict, open("%s/security_groups_dict.pickle.tmp" % self.config_persistence_dir, "wb"))

        self.logger.debug("In memory data refreshed from AWS for region [%s] and serialized to disk!\n" % region_string)


    def build_initial_security_groups_dict(self, ec2_conn):
        aws_security_group_list = ec2_conn.get_all_security_groups()
        security_groups_dict = dict()

        for security_group in aws_security_group_list:
            sg_dict = dict()
            sg_dict['sg_name'] = security_group.name
            sg_dict['hosts'] = list() #Hosts is empty just for initialization

            security_groups_dict[security_group.id] = sg_dict

        return security_groups_dict

def main():
    amazonInstanceDataCollector = AmazonInstanceDataCollector(None)
    
    for region_string in amazonInstanceDataCollector.config_supported_regions:
        amazonInstanceDataCollector.loadInstanceDataFromAWS(region_string)
        
        amazonInstanceDataCollector.logger.debug("Metadata refreshed for all regions.\n")

if __name__ == "__main__":
    main()