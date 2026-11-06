"""Checks AAS files with aas-test-engines, without any Qt dependency."""

import aas_test_engines.file as test_engines_file_check

# aas-test-engines has no release for V3.1 yet, so it checks against V3.0.
CHECKED_VERSION = "V3.0"


def checkFile(file: str):
    """Check an AAS file against the metamodel version aas-test-engines knows.

    Files are opened in binary mode: an AASX is a ZIP archive, and XML and JSON
    files carry their own encoding.

    :param file: path of a file with the extension .xml, .json or .aasx
    :return: the aas-test-engines result, which can be rendered with to_html()
    :raise TypeError if the file extension is not supported
    """
    with open(file, "rb") as f:
        if file.endswith(".xml"):
            return test_engines_file_check.check_xml_file(f)
        elif file.endswith(".json"):
            return test_engines_file_check.check_json_file(f)
        elif file.endswith(".aasx"):
            return test_engines_file_check.check_aasx_file(f)
        raise TypeError("File of unknown type:", file)
