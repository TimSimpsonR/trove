import httplib2
import json
import os
import re
import sys
import time
from urlparse import urlparse

from proboscis.asserts import *
from troveclient.compat.client import TroveHTTPClient
from trove.tests.config import CONFIG
from trove.openstack.common.processutils import execute
from trove.openstack.common.processutils import ProcessExecutionError

print_req = True



def shorten_url(url):
    parsed = urlparse(url)
    if parsed.query:
        method_url = parsed.path + '?' + parsed.query
    else:
        method_url = parsed.path
    return method_url


class SnippetWriter(object):

    def __init__(self, conf, get_replace_list):
        self.conf = conf
        self.get_replace_list = get_replace_list

    def output_request(self, user_details, name, url, output_headers, body,
                       content_type, method, static_auth_token=True):
        headers = []
        parsed = urlparse(url)
        method_url = shorten_url(url)
        headers.append("%s %s HTTP/1.1" % (method, method_url))
        headers.append("User-Agent: %s" % output_headers['User-Agent'])
        headers.append("Host: %s" % parsed.netloc)
        # static_auth_token option for documentation purposes
        if static_auth_token:
            output_token = '87c6033c-9ff6-405f-943e-2deb73f278b7'
        else:
            output_token = output_headers['X-Auth-Token']
        headers.append("X-Auth-Token: %s" % output_token)
        headers.append("Accept: %s" % output_headers['Accept'])
        print("OUTPUT HEADERS: %s" % output_headers)
        headers.append("Content-Type: %s" % output_headers['Content-Type'])
        self.write_file(user_details, name, "-%s.txt" % content_type, url,
                        method, "request", output='\n'.join(headers))

        pretty_body = self.format_body(body, content_type)
        self.write_file(user_details, name, ".%s" % content_type, url,
                        method, "request", output=pretty_body)

    def output_response(self, user_details, name, content_type, url, method,
                        resp, body):
        output_list = []
        version = "1.1"  # if resp.version == 11 else "1.0"
        lines = [
            ["HTTP/%s %s %s" % (version, resp.status, resp.reason)],
            ["Content-Type: %s" % resp['content-type']],
            ["Via: %s" % resp['via']],
            ["Content-Length: %s" % resp['content-length']],
            ["Date: Mon, 18 Mar 2013 19:09:17 GMT"],
            ["Server: %s" % resp["server"]],
        ]
        new_lines = [x[0] for x in lines]
        joined_lines = '\n'.join(new_lines)

        self.write_file(user_details, name, "-%s.txt" % content_type, url,
                        method, "response", output=joined_lines)

        if body:
            pretty_body = self.format_body(body, content_type)
            self.write_file(user_details, name, ".%s" % content_type, url, method,
                            "response", output=pretty_body)

    def format_body(self, body, content_type):
        assert content_type == 'json'
        try:
            if self.conf['replace_dns_hostname']:
                before = r'\"hostname\": \"[a-zA-Z0-9-_\.]*\"'
                after = '\"hostname\": \"%s\"' % self.conf[
                    'replace_dns_hostname']
                body = re.sub(before, after, body)
            return json.dumps(json.loads(body), sort_keys=True, indent=4)
        except Exception:
            return body or ''

    def write_request_file(self, user_details, name, content_type, url, method,
                           req_headers, request_body):
        if print_req:
            print("\t%s req url:%s" % (content_type, url))
            print("\t%s req method:%s" % (content_type, method))
            print("\t%s req headers:%s" % (content_type, req_headers))
            print("\t%s req body:%s" % (content_type, request_body))
        self.output_request(user_details, name, url, req_headers, request_body,
                            content_type, method)

    def write_response_file(self, user_details, name, content_type, url,
                            method, resp, resp_content):
        if print_req:
            print("\t%s resp:%s" % (content_type, resp))
            print("\t%s resp content:%s" % (content_type, resp_content))
        self.output_response(user_details, name, content_type, url, method,
                             resp, resp_content)

    def write_file(self, user_details, name, content_type, url, method,
                   in_or_out, output):
        filename = "%s/db-%s-%s%s" % (self.conf['directory'],
                                      name.replace('_', '-'), in_or_out,
                                      content_type)
        with open(filename, "w") as file:
            output = output.replace(user_details['tenant'], '1234')
            if self.conf['replace_host']:
                output = output.replace(user_details['api_url'],
                                        self.conf['replace_host'])
                pre_host_port = urlparse(user_details['service_url']).netloc
                post_host = urlparse(self.conf['replace_host']).netloc
                output = output.replace(pre_host_port, post_host)
            output = output.replace("fake_host", "hostname")
            output = output.replace("FAKE_", "")
            print("\n\n")
            for resource in self.get_replace_list():
                print("REPLACING %s with %s" % (resource[0], resource[1]))
                output = output.replace(str(resource[0]), str(resource[1]))
            print("\n\n")

            file.write(output)


# This method is mixed into the client class.
# It requires the following fields: snippet_writer, content_type, and
# "name," the last of which must be set before each call.
def write_to_snippet(self, args, kwargs, resp, body):
    if self.name is None:
        raise RuntimeError("'name' not set before call.")
    url = args[0]
    method = args[1]
    request_headers = kwargs['headers']
    request_body = kwargs.get('body', None)
    response_headers = resp
    response_body = body

    # Log request
    user_details = {
        'api_url': self.service_url,
        'service_url': self.service_url,
        'tenant': self.tenant,
    }
    self.snippet_writer.write_request_file(user_details, self.name,
                                           self.content_type, url, method,
                                           request_headers, request_body)
    self.snippet_writer.write_response_file(user_details, self.name,
                                            self.content_type, url, method,
                                            response_headers, response_body)

    # Create a short url to assert against.
    short_url = url
    base_url = self.service_url
    for prefix in (base_url):
        if short_url.startswith(prefix):
            short_url = short_url[len(prefix):]
    self.old_info = {
        'url': shorten_url(short_url),
        'method': method,
        'request_headers': request_headers,
        'request_body': request_body,
        'response_headers': response_headers,
        'response_body': response_body
    }


def add_fake_response_headers(headers):
    """Fakes Repose and all that jazz."""
    if 'via' not in headers:
        headers['via'] = "1.1 Repose (Repose/2.6.7)"
    if 'server' not in headers:
        headers['server'] = 'Jetty(8.0.y.z-SNAPSHOT)'
    if 'date' not in headers:
        date_string = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())
        headers['date'] = date_string


class JsonClient(TroveHTTPClient):

    content_type = 'json'

    def http_log(self, args, kwargs, resp, body):
        add_fake_response_headers(resp)
        self.pretty_log(args, kwargs, resp, body)

        def write_snippet():
            return write_to_snippet(self, args, kwargs, resp, body)

        self.write_snippet = write_snippet
