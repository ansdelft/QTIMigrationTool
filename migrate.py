#! /usr/bin/env python3

"""Copyright (c) 2004-2008, University of Cambridge.

All rights reserved.

Redistribution and use of this software in source and binary forms
(where applicable), with or without modification, are permitted
provided that the following conditions are met:

 *  Redistributions of source code must retain the above copyright
    notice, this list of conditions, and the following disclaimer.

 *  Redistributions in binary form must reproduce the above
    copyright notice, this list of conditions, and the following
    disclaimer in the documentation and/or other materials provided with
    the distribution.

 *  Neither the name of the University of Cambridge, nor the names of
    any other contributors to the software, may be used to endorse or
    promote products derived from this software without specific prior
    written permission.

THIS SOFTWARE IS PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""


MIGRATION_VERSION="2008-06-12"

import os, sys
from stat import *
import ipdb
import re

SPLASH_LOG=[
"IMS QTIv1.2 to QTIv2.1 Migration Tool, by Steve Lay",
"",
"Copyright (c) 2004 - 2008, University of Cambridge",
"GUI Code Copyright (c) 2004 - 2008, Pierre Gorissen",
"All Rights Reserved",
"See README file for licensing information",
"Version: %s"%MIGRATION_VERSION,
""
]

HELP_TEXT=[
	"Usage: migrate.py [options] [--cpout=output directory] [input file|directory]",
	"",
	"Recognized options:",
	"  --ucvars           : force upper case variable names",
	"  --qmdextensions    : allows metadata extension fields",
	"  --lang=<language>  : set default language",
	"  --dtdloc=<path>    : set the directory containing the QTI DTD",
	"  --forcefibfloat    : force all fib's to float type",
	"  --nocomment        : suppress comments in version 2 output",
	"  --nogui            : run in batch mode only",
	"  --help             : display this message (implies --nogui)",
	"  --version          : display version information only (implies --nogui)"
	"  --overwrite		  : If the files already exist overwrite them"
	"  --pathprepend	  : A path to prepend to file references"
	"  --createerrorfiles : If a referenced file is not found create a dummy file in its place"
]


NO_GUI=0

def fix_max_choices(question_text):
	response_identifiers = re.findall(r"<choiceInteraction responseIdentifier=\"(.*?)\"", question_text)
	for response_identifier in response_identifiers:
		response_cases = re.findall(r'<(responseIf>.*?</responseIf|responseElseIf>.*?</responseElseIf)', question_text, re.DOTALL)
		amount_correct = 0
		for response_case in response_cases:
			if not f"identifier=\"{response_identifier}\"" in response_case:
				continue

			if response_case.find(f"<variable identifier=\"{response_identifier}\"/>") != -1 and len(re.findall(r'<baseValue baseType="(integer|float)">(0|-.*?)</baseValue>', response_case)) < 1:
				amount_correct += 1

		replacement = fr"<choiceInteraction responseIdentifier=\"{response_identifier}\" shuffle=\"true\" maxChoices=\"{amount_correct}\">"
		question_text = question_text.replace(fr"<choiceInteraction responseIdentifier=\"{response_identifier}\" shuffle=\"true\" maxChoices=\"0\">", replacement)
	return question_text


def fix_latex(question_text):
	return question_text.replace('[tex]', '$$').replace('[/tex]', '$$')

def fix_fill_question(question_text):
	if 'render_fib' in question_text:
		extended_texts = re.findall(r'<extendedTextInteraction.*?/>', question_text)
		question_text = question_text.replace('extendedTextInteraction', 'textEntryInteraction')
		expected_lengths = re.findall(r'(expectedLength="(.*?)")', question_text)
		for expected_lenth, length in expected_lengths:
			if int(length) <= 80:
				continue

			replacement = expected_lenth.replace(length, '80')
			question_text = question_text.replace(expected_lenth, replacement)

		for extended_text in extended_texts:
			identifier = re.findall(r'responseIdentifier="(.*?)"', extended_text)[0]
			answer_value = re.findall(fr'<baseValue.*?identifier="{identifier}">(.*?)</baseValue>', question_text, re.DOTALL)
			if answer_value == []:
				answer_value = 1
			else:
				answer_value = answer_value[0]
			response_declaration = re.findall(fr'(<responseDeclaration identifier="{identifier}".*?/)>', question_text, re.DOTALL)[0]
			replacement = f"{response_declaration[:-1]}><correctResponse><value>{answer_value}</value></correctResponse></response_declaration"
			question_text = question_text.replace(response_declaration, replacement)

	return question_text

def fix_hotspot_question(question_text):
	if 'selectPointInteraction' in question_text:
		coords = re.findall(r'(<inside shape="(.*?)".*?coords="(.*?)">.*?</inside>)', question_text)
		shape = coords[0][1]
		x1, y1, y2, x2 = coords[0][2].split(' ')
		x2 = int(x1) + int(x2) - int(y1)
		y2 = int(y1) + int(y2) - int(x1)
		question_text = question_text.replace(coords[0][0], f"<areaMapping><areaMapEntry shape=\"{shape}\" coords=\"{x1},{y1},{x2},{y2}\" mappedValue=\"1\"/></areaMapping>")
	
	return question_text

def remove_p_tags(question_text):
	return question_text.replace('<div class="html"><p></div>', '').replace('<div class="text"><p></div>', '')

def run(source_folder, destination_folder):
	wd=os.path.dirname(__file__)
	sys.path.append(os.path.join(wd,"lib"))
	import imsqtiv1

	options=imsqtiv1.QTIParserV1Options()
	fileNames=[]
	OVERWRITE=False

	options.cpPath = destination_folder
	fileNames = [source_folder]

	parser=imsqtiv1.QTIParserV1(options)
	parser.ProcessFiles(os.getcwd(),fileNames)
	parser.DumpCP()

	files = [ file.path for file in os.scandir(f"{options.cpPath}/assessmentItems") if file.is_file()]
	print(len(files))
	for xml_file in files:
		question_xml = open(xml_file, 'r')
		question_text = question_xml.read()
		item_body = re.findall(r'<itemBody>.*?</itemBody', question_text, re.DOTALL)
		if len(item_body) == 0:
			continue 
		
		question_text = fix_max_choices(question_text)
		question_text = fix_latex(question_text)
		question_text = fix_fill_question(question_text)
		question_text = fix_hotspot_question(question_text)
		question_text = remove_p_tags(question_text)

		filename = xml_file.replace(f'{options.cpPath}/', '')
		folder_name = options.cpPath.replace('/assessmentItems', '')
		
		os.remove(f'{folder_name}/{filename}')
		file = open(f'{folder_name}/{filename}', "a")
		file.write(question_text)
		file.close()

	filenames=None
	parser=None

