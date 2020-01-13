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
        parser_handler.error(f'The file {filename} does not exist!')
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
    return element.find(f'stringProp[@name="{attribute_name}"]').text.replace('$', '')


def get_params(element):
    node = element.find('elementProp/collectionProp/elementProp/stringProp[@name="Argument.value"]')
    if node is not None:
        if not node.text:
            return
        try:
            return str(json.loads(node.text)).replace('$', '')
        except JSONDecodeError:
            return


def get_header(element, path='HeaderManager/collectionProp/elementProp'):
    node = element.findall(path)
    if not node:
        return
    headers = {}
    for element_prop in node:
        key = element_prop.find(HEADER_NAME_TAG).text.replace('$', '')
        value = element_prop.find(HEADER_VALUE_TAG).text.replace('$', '')
        headers[key] = value
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


def get_urls_from_xml(root):
    urls = []
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


def get_json_path(json_path_exprs):
    return json_path_exprs[1:].split(".")[1:]


def get_post_processors(element):
    result = ''
    json_post_processors = element.findall('.//JSONPostProcessor')
    for json_post_processor in json_post_processors:
        variable_name = json_post_processor.find('stringProp[@name="JSONPostProcessor.referenceNames"]').text
        json_path_exprs = json_post_processor.find('stringProp[@name="JSONPostProcessor.jsonPathExprs"]').text
        json_path = get_json_path(json_path_exprs)
        result += f'self.variables["{variable_name}"] = self.multiple_get(response_json, {json_path}) or self.variables["{variable_name}"]\n                '  # This is not a mistake
    return result


def generate_file(base_file, filename='locustfile.py'):
    xml_root = get_xml_root(filename=base_file)
    urls = get_urls_from_xml(root=xml_root)
    additional_variables = ''
    post_processor = get_post_processors(element=xml_root)
    with open(f'{pathlib.Path(__file__).parent}/locustfile.template') as template:
        template_file = Template(template.read())
        result_data = template_file.substitute(
            urls=urls,
            additional_variables=additional_variables,
            post_processor=post_processor
        )

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
