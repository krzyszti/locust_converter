import argparse
import json
import os
import pathlib
from json import JSONDecodeError
from string import Template
from lxml import etree
from lxml.etree import XMLSyntaxError

from yapf.yapflib.yapf_api import FormatCode

HEADER_NAME_TAG = 'stringProp[@name="Header.name"]'
HEADER_VALUE_TAG = 'stringProp[@name="Header.value"]'


def is_valid_file(parser_handler, filename):
    if not os.path.exists(filename):
        parser_handler.error(f"The file {filename} does not exist!")
    else:
        return filename


def get_xml_root(filename):
    try:
        with open(filename) as file:
            return etree.parse(file)
    except XMLSyntaxError:
        raise Exception(f'File {filename} is not correct XML file')


def get_element_tags(element, test_tag='.//HTTPSamplerProxy'):
    return element.findall(test_tag)


def get_attribute_value(element, attribute_name=''):
    return element.find(f'stringProp[@name="{attribute_name}"]').text


def get_params(element):
    node = element.find('elementProp/collectionProp/elementProp/stringProp[@name="Argument.value"]')
    if node is not None:
        if not node.text:
            return
        try:
            return str(json.loads(node.text))
        except JSONDecodeError:
            return


def get_header(element, path='HeaderManager/collectionProp/elementProp'):
    node = element.findall(path)
    if not node:
        return
    headers = {}
    for element_prop in node:
        headers[element_prop.find(HEADER_NAME_TAG).text] = element_prop.find(HEADER_VALUE_TAG).text
    return headers


def get_base_header(root):
    """
    Base header used in all test cases is defined in the end of the jmeter XML file
    """
    element = root.find('.//hashTree/hashTree/HeaderManager')
    return get_header(element, path='collectionProp/elementProp')


def get_test_case_header(element):
    """
    Header is the next element in the XML tree.
    In order to get the header details, we need to check the next element after HTTPSamplerProxy.
    If  "HeaderManager" does not exist in the next element, this test case has no specific header.
    """
    return get_header(element.getnext())


def get_urls_from_xml(filename):
    urls = []
    root = get_xml_root(filename=filename)
    base_header = get_base_header(root)
    for element in get_element_tags(root):
        enabled = element.attrib.get('enabled')
        if enabled:
            endpoint = get_attribute_value(element, 'HTTPSampler.path')
            method = get_attribute_value(element, 'HTTPSampler.method')
            params = get_params(element)
            headers = get_test_case_header(element) or base_header
            url = f"{{'method': '{method}', 'url': '{endpoint}', 'params': {params}, 'headers': {headers}}},"
            urls.append(url)
    return ''.join(urls)


def generate_file(base_file, filename='locustfile.py'):
    urls = get_urls_from_xml(filename=base_file)
    additional_variables = ''
    with open(f'{pathlib.Path(__file__).parent}/locustfile.template') as template:
        template_file = Template(template.read())
        result_data = template_file.substitute(urls=urls, additional_variables=additional_variables)

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
