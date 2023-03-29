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

if __name__ == '__main__':
	wd=os.path.dirname(__file__)
	sys.path.append(os.path.join(wd,"lib"))
	try:
		import imsqtiv1
	except:
		print("Problem loading extra modules in %s/lib"%wd)
		print(" ...error was: %s (%s)"%(str(sys.exc_info()[0]),str(sys.exc_info()[1])))
		sys.exit(1)

	options=imsqtiv1.QTIParserV1Options()
	fileNames=[]
	OVERWRITE=False
	for x in sys.argv[1:]:
		# check for options here
		if x[:8].lower()=="--cpout=":
			options.cpPath=os.path.abspath(x[8:])
		elif x.lower()=="--ucvars":
			options.ucVars=1
		elif x.lower()=="--qmdextensions":
			options.qmdExtensions=1
			if not options.vobject:
				SPLASH_LOG.append("Warning: qmd_author and qmd_organization support disabled")
				SPLASH_LOG.append(" ...try installing VObject.  See: http://vobject.skyhouseconsulting.com/")
		elif x.lower()=="--forcefibfloat":
			options.forceFloat=1
		elif x[:7].lower()=="--lang=":
			options.lang=x[7:]
		elif x.lower()=="--nocomment":
			options.noCmment=1
		elif x[:9].lower()=="--dtdloc=":
			options.dtdDir=os.path.abspath(x[9:])
		elif x.lower()=="--help":
			SPLASH_LOG=SPLASH_LOG+HELP_TEXT
			NO_GUI=1
		elif x.lower()=="--version":
			NO_GUI=1
			fileNames=[]
			break
		elif x.lower()=="--nogui":
			NO_GUI=1
		elif x.lower()=="--overwrite":
			OVERWRITE=1
		elif x[:14].lower()=="--pathprepend=":
			options.prepend_path = x[14:]
		elif x.lower()=="--createerrorfiles":
			options.create_error_files = 1
		else:
			fileNames.append(x)

	if not options.dtdDir:
		options.dtdDir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'schemas'))

	if options.cpPath and os.path.exists(options.cpPath):
		if os.path.isdir(options.cpPath):
				SPLASH_LOG.append("Warning: CP Directory already exists, overwriting.")
		else:
			SPLASH_LOG.append("Warning: --cpout points to file, ignoring")
			options.cpPath=''

	if not NO_GUI:
		try:
			import gui
		except:
			SPLASH_LOG.append("Problem loading GUI module, defaulting to command-line operation")
			SPLASH_LOG.append(" ...error was: %s (%s)"%(str(sys.exc_info()[0]),str(sys.exc_info()[1])))
			NO_GUI=1

	if NO_GUI:
		for line in SPLASH_LOG:
			print(line)
		parser=imsqtiv1.QTIParserV1(options)
		parser.ProcessFiles(os.getcwd(),fileNames)
		parser.DumpCP()
	else:
		print("Application is active...")
		print("Do not close this window because it will also close the GUI!")
		app = gui.MyApp(SPLASH_LOG,options,fileNames)
		app.MainLoop()

	files = [ file.path for file in os.scandir(f"{options.cpPath}/assessmentItems") if file.is_file()]
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
	sys.exit(0)

