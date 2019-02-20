#!/usr/bin/python

import NicTool
import logging
from dns import reversename
import netaddr
import ConfigParser
import string
import nmap
import itertools


class PyNicTool(object):
  def __init__(self, username, password, nictoolUrl):
    self.nictool = NicTool.NicTool(username, password, nictoolUrl)

  def add_record(self, fqdn, record_type, value, ttl=3600):
    name, p, zone = fqdn.rstrip('.').partition('.')
    original_records = self.search_records(fqdn, record_type)
    if original_records is not None:
      return
    args = {
      "nt_zone_record_id": '',
      "nt_zone_id": self.nictool.find_zone(zone),
      "name": name,
      'type': record_type,
      'address': value,
      'ttl': ttl,
      }
    result = self.nictool.new_zone_record(args)
    return result.nt_zone_record_id

  def add_bidirectional_record(self, fqdn, ip, ttl=3600):
    reverse_fqdn = reversename.from_address(ip).to_text().rstrip('.')
    ptr_record_id = self.add_record(reverse_fqdn, 'PTR', fqdn + '.', ttl=ttl)
    a_record_id = self.add_record(fqdn, 'A', ip, ttl=ttl)
    success = ptr_record_id is not None and a_record_id is not None
    return {'success': success, 'ptr_record_id': ptr_record_id, 'a_record_id': a_record_id}

  def search_records(self, fqdn, record_type):
    name, p, zone = fqdn.rstrip('.').partition('.')
    zone_id = self.nictool.find_zone(zone)
    result = self.nictool.get_zone_records({
      "nt_zone_id": zone_id,
      "0_field": "type",
      "0_value": record_type,
      "0_option": "equals",
      "1_inclusive": "And",
      "1_field": "name",
      "1_value": name,
      "1_option": "equals",
      "Search": 1,
      })
    if result.total > 0:
      return result.records

  def get_all_records(self, zone):
    zone_id = self.nictool.find_zone(zone)
    records = self.nictool.get_zone_records({
        "nt_zone_id": zone_id,
        "limit": 255,
        })
    return records

  def ip_available(self, ip):
    nm = nmap.PortScanner()
    r = nm.scan(hosts=ip, arguments='-n -sn')
    if r['scan'][ip]['status']['state'] != 'up':
      if not self.search_records(reversename.from_address(ip).to_text().rstrip('.'), 'PTR'):
        return True
    return False

  def iter_unused_ips(self, cidr, reserved_num=50):
    nm = nmap.PortScanner()
    net = netaddr.IPNetwork(cidr)
    reserved = set([ h for h in itertools.islice(net.iter_hosts(), reserved_num) ])
    used = []
    for subnet in net.subnet(24):
      zone = reversename.from_address(str(subnet.ip)).parent().to_text().rstrip('.')
      r = self.get_all_records(zone)
      used = set([ netaddr.IPAddress(('.').join(map(str, list(subnet.ip.words[:3]) + [i.name]))) for i in r.records ])
      for ip in subnet.iter_hosts():
        if ip not in reserved and ip not in used:
          r = nm.scan(hosts=str(ip), arguments='-n -sn')
          if r['scan'][str(ip)]['status']['state'] != 'up':
            yield ip

  def get_unused_ips(self, cidr, count=5, reserved_num=50):
    return list(itertools.islice(self.iter_unused_ips(cidr, reserved_num=reserved_num), count))

  def get_unused_ip(self, cidr, reserved_num=50):
    return self.iter_unused_ips(cidr, reserved_num=reserved_num).next()

  def get_similar_ips(self, subnet_1, subnet_2):
    ips = map(self.get_unused_ips, [subnet_1, subnet_2])
    return [ (ip1, ip2) for ip1 in ips[0] for ip2 in ips[1] if ip1.words[3] == ip2.words[3] ]



if __name__ == "__main__":
  logging.getLogger(__name__)
  logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.WARN)
  config = ConfigParser.RawConfigParser(allow_no_value=True)
  config.read('pynictool.conf')
  username = config.get('main', 'username')
  password = config.get('main', 'password')
  url = config.get('main', 'url')

  nictool = PyNicTool(username, password, url)
