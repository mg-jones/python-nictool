#!/usr/bin/python
'''Module for accessing the NicTool API through the SOAP protocol.
Docs and available functions at https://www.nictool.com/docs/api/
'''

import logging
import string
import time
import urllib2

from beaker.cache import CacheManager
from SOAPpy import parseSOAPRPC


LOGGER = logging.getLogger(__name__)
CACHE = CacheManager()


class NicTool(object):
    '''API object'''
    def __init__(self, username, password, nictoolUrl, soapUrl):
        self.soap_blob = string.Template('''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/"
            xmlns:apachens="http://xml.apache.org/xml-soap"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            soap:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"
            xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body><$method xmlns="$url">
        $body </$method></soap:Body></soap:Envelope>''')
        self.nictool_url = nictoolUrl
        self.soap_url = soapUrl
        self.activity_timestamp = 0
        self.username = username
        self.password = password
        self.nt_user_session = None

    def assemble_body(self, args):
        '''Build SOAP body with key/value pairs'''
        typemap = (
            (int, "int"),
            (float, "float"),
            (str, "string")
        )
        if isinstance(args, dict):
            body = '<c-gensym6 xsi:type="apachens:Map">'
            for key, value in args.iteritems():
                for vtype, vstring in typemap:
                    if isinstance(value, vtype):
                        break
                body = body + '''<item><key xsi:type="xsd:string">%s</key><value xsi:type="xsd:%s">%s</value></item>\n''' % (key, vstring, value)
            body = body + '</c-gensym6>'
        return body

    def parseSOAP(self, soap):
        '''Parse a SOAP body'''
        soap_body = parseSOAPRPC(soap)
        try:
            count = 0
            for i in soap_body.__dict__.keys():
                if i[0] != "_":  # Don't count the private stuff
                    count += 1
                    soap_value = getattr(soap_body, i)
            if count == 1:  # Only one piece of data, bubble it up
                soap_body = soap_value
        except:
            pass
        return soap_body

    def _make_api_call(self, method, arguments):
        LOGGER.debug("%s %s" % (method, str(arguments)))
        seconds_idle = time.time() - self.activity_timestamp
        self.activity_timestamp = time.time()
        if seconds_idle > 120 or (self.nt_user_session is None and not arguments.get("username")):
            self.nt_user_session = None
            self.nt_user_session = self.login(username=self.username, password=self.password, nt_user_session='').nt_user_session
        arguments["nt_user_session"] = self.nt_user_session
        body = self.assemble_body(arguments)
        post_body = self.soap_blob.substitute(method=method, body=body, url=self.soap_url)
        LOGGER.debug(post_body)
        req = urllib2.Request(self.nictool_url)
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        soapaction = self.soap_url + '#' + method
        req.add_header('SOAPAction', soapaction)
        req.add_header('Content-Type', 'text/xml')
        LOGGER.debug(req)
        response_xml = opener.open(req, data=post_body).read()
        LOGGER.debug(response_xml)
        response = self.parseSOAP(response_xml)
        if "error_code" in dir(response) and response.error_msg != "OK":
            raise Exception('"%s request failed [%s]: %s' % (method, response.error_code, response.error_msg))
        return response

    def __getattr__(self, name):
        def handlerFunction(*args, **kwargs):
            if kwargs:
                return self._make_api_call(name, kwargs)
            return self._make_api_call(name, args[0])
        return handlerFunction

    @CACHE.cache('nictoolcache', expire=600)
    def find_zone(self, wanted_zone):
        '''
        Finds the zone id for a given zone
        wanted_zone - The string of the zone you are looking for.
        Returns the nt_zone_id or raises an exception if it is unable to find the zone.
        '''
        zone_id = None
        start = 0
        remaining = 1
        LOGGER.debug("Finding zone " + wanted_zone)
        while remaining > 0 and zone_id is None:
            args = {
                "Search": 1,
                "nt_group_id": 1,
                "include_subgroups": 1,
                "exact_match": 1,
                "quick_search": 0,
                "start": start,
                "limit": 255,
                "0_field": "zone",
                "0_value": wanted_zone,
                "0_option": "equals",
            }
            response = self.get_group_zones(args)
            if response.total == 1:
                zone_id = response.nt_zone_id
            for current_zone in response.zones:
                if current_zone.zone.upper() == wanted_zone.upper():
                    zone_id = current_zone.nt_zone_id
                    LOGGER.debug("Found zone id %d" % zone_id)
                    return zone_id
            offset = response.page * response.limit
            remaining = response.total - offset
            LOGGER.debug("Continuing search at offset %d of %d." % (offset, response.total))
            start = offset
        LOGGER.error("Unable to find zone %s" % wanted_zone)
        raise Exception("Unable to find zone %s" % wanted_zone)

    def find_record_in_zone(self, zone, record, record_type):
        '''Find a record of specified type in provided zone'''
        zone_id = self.find_zone(zone)
        response = self.get_zone_records({
            "Search": 1,
            "nt_zone_id": zone_id,
            "0_field": 'type',
            "0_value": record_type,
            "0_option": 'equals',
            '1_inclusive': 'And',
            '1_field': 'name',
            '1_value': record,
            '1_option': 'equals',
            'exact_match': 1
        })
        return response

    def delete_record_from_zone(self, zone, record, record_type):
        '''Delete a record of specified type from provided zone'''
        response = self.find_record_in_zone(zone, record, record_type)
        if response['total'] < 1:
            LOGGER.debug("Unable to find %s [%s] to delete from %s" % (record, record_type, zone))
            return
        if response['total'] > 1:
            LOGGER.warn("%d records matched %s [%s] from %s" % (response['total'], record, record_type, zone))
            return
        LOGGER.debug("Deleting %s [%s] from %s" % (record, record_type, zone))
        record = response['records'][0]
        response = self.delete_zone_record({
            "nt_zone_record_id": record['nt_zone_record_id']
        })
        return record

    def ip_to_arpa(self, ipaddr):
        '''Translate IP to ARPA format'''
        a, b, c, d = ipaddr.split(".")
        return d, "%s.%s.%s.in-addr.arpa" % (c, b, a)

    def hostname_to_name_zone(self, hostname):
        '''Find a zone from hostname'''
        name, _, zone = hostname.rstrip('.').partition('.')
        return name, zone

    def delete_forward_and_reverse_records(self, hostname=None, ip=None):
        '''Delete records'''
        # If a hostname is specified, delete the hostname record and the reverse record if it matches the hostname
        if hostname is not None:
            name, zone = self.hostname_to_name_zone(hostname)
            record = self.delete_record_from_zone(zone, name, "A")
            if record is not None:
                name, zone = self.ip_to_arpa(record['address'])
                ip_record = self.find_record_in_zone(zone, name, "PTR")
                if ip_record:
                    ip_record = ip_record['records'][0]
                    if ip_record['address'].rstrip('.') != hostname:  # We do this incase we have multiple A records to an IP. We don't want to delete the reverse unless its the right one
                        LOGGER.warn("Reverse record for %s [%s] does not match %s, not deleting %s.%s" % (record['address'], ip_record['address'].rstrip('.'), hostname, name, zone))
                    else:
                        record = self.delete_record_from_zone(zone, name, "PTR")
        # If an ip is specified, delete the PTR and the A record it points to
        if ip is not None:
            name, zone = self.ip_to_arpa(ip)
            record = self.delete_record_from_zone(zone, name, "PTR")
            if record is not None:
                name, _, zone = hostname.rstrip('.').partition('.')
                record = self.delete_record_from_zone(zone, name, "A")

    def add_record_to_zone(self, zone, record, record_type, address, ttl=3600, weight=10):
        '''Add a record to specified zone'''
        zone_id = self.find_zone(zone)
        addition = {
            "nt_zone_id": zone_id,
            "nt_zone_record_id": "",
            "name": record,
            "type": record_type,
            "address": address,
            "ttl": ttl
        }
        if record_type == 'MX':
            addition['weight'] = weight
        result = self.new_zone_record(addition)
        return result.nt_zone_record_id

    def add_forward_and_reverse_records(self, hostname=None, ipaddr=None, ttl=3600):
        '''Add forward and reverse record for provided hostname/IP'''
        if hostname is None or ipaddr is None:
            return
        name, zone = self.hostname_to_name_zone(hostname)
        self.add_record_to_zone(zone, name, "A", ipaddr, ttl=ttl)
        name, zone = self.ip_to_arpa(ipaddr)
        self.add_record_to_zone(zone, name, "PTR", hostname + ".", ttl=ttl)

    def add_forward_record(self, hostname=None, ipaddr=None, ttl=3600):
        '''Add a forward record'''
        if hostname is None or ipaddr is None:
            return
        name, zone = self.hostname_to_name_zone(hostname)
        self.add_record_to_zone(zone, name, "A", ipaddr, ttl=ttl)

    def add_reverse_record(self, hostname=None, ipaddr=None, ttl=3600):
        '''Add a reverse record'''
        if hostname is None or ipaddr is None:
            return
        name, zone = self.ip_to_arpa(ipaddr)
        self.add_record_to_zone(zone, name, "PTR", hostname + ".", ttl=ttl)
