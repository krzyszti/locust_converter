import argparse
import json
import os
import pathlib
from string import Template
from xml.etree import ElementTree
from xml.etree.ElementTree import ParseError

from yapf.yapflib.yapf_api import FormatCode


def is_valid_file(parser_handler, filename):
    if not os.path.exists(filename):
        parser_handler.error("The file {filename} does not exist!")
    else:
        return filename


def get_xml(filename, test_tag='.//HTTPSamplerProxy'):
    try:
        return ElementTree.parse(filename).findall(test_tag)
    except ParseError:
        raise Exception(f'File {filename} is not correct XML file')


def get_attribute_value(element, attribute_name=''):
    for node in element.findall('stringProp'):
        if node.attrib['name'] == attribute_name:
            return node.text


def get_params(element):
    node = element.find('elementProp/collectionProp/elementProp/stringProp[@name="Argument.value"]')
    if node is not None:
        if not node.text:
            return
        return str(json.loads(node.text))


def get_urls_from_xml(name):
    urls = []
    for element in get_xml(filename=name):
        enabled = element.attrib.get('enabled')
        if enabled:
            endpoint = get_attribute_value(element, 'HTTPSampler.path')
            method = get_attribute_value(element, 'HTTPSampler.method')
            params = get_params(element)
            url = f"{{'method': '{method}', 'url': '{endpoint}', 'params': {params}}},"
            urls.append(url)
    return ''.join(urls)


def generate_file(base_file, filename='locustfile.py'):
    urls = get_urls_from_xml(name=base_file)
    with open(f'{pathlib.Path(__file__).parent}/locustfile.template') as template:
        template_file = Template(template.read())
        result_data = template_file.substitute(urls=urls)

    with open(filename, 'w') as file:
        file.write(FormatCode(result_data)[0])


parser = argparse.ArgumentParser(description='Convert jmeter tests to locust.')

parser.add_argument(
    "-f",
    dest="filename",
    required=True,
    help="File name with correct jmeter tests in xml file.",
    metavar="FILE",
    type=lambda x: is_valid_file(parser, x)
)


def main():
    args = parser.parse_args()
    generate_file(base_file=args.filename)
