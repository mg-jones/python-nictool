Py-NicTool
==========

The NicTool python module utilizes the existing API with SOAP calls to retrieve, update, and manipulate
DNS records. The available API calls can be referenced in the [NicTool docs](https://www.nictool.com/docs/api/api.shtml)
and are explained in this README. Additional 'helper' functions have been added to simiplify some of the
needed requests.

# Installation
TODO

# Usage:

```py
from NicTool import NicTool

NICTOOL_SERVER = "http://nictool.example.com:8082/soap"
NICTOOL_SOAP_URL = "http://nictool.example.com/NicToolServer/SOAP"
NICTOOL_USER = "username"
NICTOOL_PASS = "password"

nc = NicTool(NICTOOL_USER, NICTOOL_PASS, NICTOOL_SERVER, NICTOOL_SOAP_URL)
```


# Functions

- find_zone(zoneName) : Retrieve the zone ID for a given zone Name  
  `>>> nc.find_zone('example.com')`  
  `123`  

- find_record_in_zone(zoneName, record, recordType) : Retrieve a record for a given zone, record Name, and Type  
  `>>> nc.find_record_in_zone('example.com', 'testing', 'A')`  
  `<SOAPpy.Types.structType s-gensym105 at 36063208>: {'end': 30, 'start': 1, 'total_pages': 1, 'page': 1, 'records': [<SOAPpy.Types.structType item at 36063064>: {'nt_zone_record_id': 12345, 'nt_zone_id': 123, 'name': 'testing', 'weight': None, 'deleted': 0, 'ttl': 3600, 'period': None, 'delegate_add_records': None, 'priority': None, 'other': None, 'delegate_delete_records': None, 'address': '1.2.3.4', 'queries': None, 'type': 'A', 'description': None}], 'limit': 30, 'total': 1, 'error_code': 200, 'error_msg': 'OK'}`  

- ip_to_arpa(ipaddr) : Return the arpa reverse zone name for a given IP  
  `>>> nc.ip_to_arpa('1.2.3.4')`  
  `('2', '3.2.1.in-addr.arpa')`  

- hostname_to_name_zone : Return the zone Name for a given hostname  
  `>>> nc.hostname_to_name_zone('testhostprod001.example.com')`  
  `('testhostprod001', 'example.com')`  

- add_record_to_zone(zoneName, recordName, recordType, address, ttl) : Add a record to a given zone  
  `>>> nc.add_record_to_zone('example.com', 'testhostprod001.example.com', 'A', '3.4.5.6', 3600)`  

- add_forward_and_reverse(hostname, ip, ttl) : Lookup zone for hostname and add forward and reverse records  
  `>>> nc.add_forward_and_reverse_records('testhostprod001.example.com', '3.4.5.6', 3600)`  

- add_forward_record(hostname, ip, ttl) : Lookup zone for hostname and add forward record  
- add_reverse_record(hostname, ip, ttl) : Lookup zone for hostname and add reverse record  

- delete_forward_and_reverse_records(hostname|ip) : Delete the forward and reverse records for a provided hostname OR ip-address  
  `>>> nc.delete_forward_and_reverse('testhostprod001.example.com')`  

- delete_record_from_zone(zoneName, record, recordType) : Delete a record from a zone  
  `>>> nc.delete_record_from_zone('example.com', 'testrecord', 'A')`  
