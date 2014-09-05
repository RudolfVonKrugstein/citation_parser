import requests
import sys
import re
import json
import codecs
import sys

errorDois = []
warningDois = []

if len(sys.argv) != 4:
    print "Usage: python citation_parser.py <citation-file> <output-file> <csv-file>"
    exit(0)

inputFile = sys.argv[1]
outputFile = sys.argv[2]
csvFile = sys.argv[3]
f = open(outputFile,"w")
f.close()
f = open(csvFile,"w")
f.close()

f = codecs.open(inputFile, "r", "utf-8")
content = f.read()
repl_regex=r"(^|\n)[1-9][0-9]*\."
content = re.sub(repl_regex,"\n\n",content)
# remove empty lines
content = re.sub(r'\n\s+\n',"\n\n",content)

citations = content.split("\n\n")
print citations
citations = map(lambda s: s.replace("\n"," "), citations)
citations = map(lambda s: s.strip(), citations)
citations = filter(lambda s: len(s) != 0, citations)

def removeEndingS(val):
    while True:
        if (val.find('s ') == -1):
            return val
        pos = val.find('s ')
        val = val[0:pos]+val[pos+1:]

def fuzzyStringFind(outside, inside):
    inside = re.sub(r'[^\x00-\x7F]+','', inside)
    outside = re.sub(r'[^\x00-\x7F]+','', outside)
    inside = inside.lower()
    outside = outside.lower()
    inside = removeEndingS(inside)
    outside = removeEndingS(outside)
    inside = re.sub(r'(^|[^a-zA-Z])a([^a-zA-Z]|$)','', inside)
    outside = re.sub(r'(^|[^a-zA-Z])a([^a-zA-Z]|$)','', outside)
    inside = re.sub(r'(^|[^a-zA-Z])the([^a-zA-Z]|$)','', inside)
    outside = re.sub(r'(^|[^a-zA-Z])the([^a-zA-Z]|$)','', outside)
    inside = re.sub(r'\<.*\>','', inside)
    outside = re.sub(r'\<.*\>','', outside)
    inside = re.sub(r'&.*;','', inside)
    outside = re.sub(r'&.*;','', outside)
    inside = re.sub(r'[-, .\'"(){}\[\]!?:;]+','', inside)
    outside = re.sub(r'[-, .\'"(){}\[\]!?:;]+','', outside)
    # shorten inside to improve match
    inside = inside[0:-len(inside)/5]

    print ("")
    print (outside)
    print ("")
    print (inside)
    print ("")

    return outside.find(inside) != -1

print "File parsed, found",len(citations),"citations"

def searchForDoiOnline(citation):
    print "Searching for doi online ..."
    altDois = []
    url = "http://search.labs.crossref.org/dois"
    values = {'q' : citation, 'sort' : "score"}
    r = requests.get(url, params=values)
    try:
        doi = r.json()[0].get('doi')
        print "Found doi online: ",doi
        for i in xrange(1,10):
            if len(r.json()) > i:
                altDois.append(r.json()[i].get('doi'));
    except:
        print "Found no doi, only this: "
        print json.dumps(r.json(), sort_keys=True, indent=4, separators=(',', ': '))
        doi = "NOT FOUND"
    return doi,altDois

def getJsonForDoi(doi):
    r = requests.get(doi, headers={'Accept' : 'application/vnd.citationstyles.csl+json'})
    return r.json()

for citation in citations:
    print "Working with"
    print citation
    regex = "10[.][0-9]{4,}(?:[.][0-9]+)*/(?:(?![\"&\'<>,])\S)+[0-9a-zA-Z]"
    result = re.search(regex, citation)
    if result:
        doi = "http://dx.doi.org/" + result.group(0)
        print "Found doi in citation: ",doi
        foundOnline = False
    else:
        (doi,altDois) = searchForDoiOnline(citation)
        foundOnline = True

    try:
        jsonData = getJsonForDoi(doi)
    except:
        if not foundOnline:
            doi,altDois = searchForDoiOnline(citation)
        try:
            jsonData = getJsonForDoi(doi)
            foundOnline = True
            warningDois.append((doi,citation))
        except:
            errorDois.append((doi,citation))
            continue
    #print "This is what I got for the doi:"
    #print json.dumps(jsonData, sort_keys=True, indent=4, separators=(',', ': '))
    # do the formating
    handled = False
    while not handled:
        try:
            names = jsonData.get('author')
            namesString = names[0].get('family') + ", " + names[0].get('given')
            for i in xrange(1,len(names)):
                namesString = namesString + ", " + names[i].get('given') + " " + names[i].get('family')
            fNamesString = namesString + ", "
            yearString = str(jsonData.get('issued').get('date-parts')[0][0])
            fYearString = yearString + ". "
            titleString = jsonData.get('title')
            fTitleString = titleString + ". "
            journalString = jsonData.get('container-title')
            fJournalString = journalString + ". "

            if (jsonData.has_key('volume')):
                volumeString = jsonData.get('volume')
                fVolumeString = volumeString
            else:
                volumeString = ""
                fVolumeString = ""
            if (jsonData.has_key('page')):
                pageString = jsonData.get("page")
                if (jsonData.has_key('volume')):
                    fPageString = ", " + pageString + "."
                else:
                    fPageString = pageString + "."
            else:
                pageString = ""
                if (jsonData.has_key('volume')):
                    fPageString = "."
                else:
                    fPageString = ""
            # ok, if we found this online, we might want to verify this ...
            if foundOnline:
                if (not fuzzyStringFind(citation,titleString)) or (not fuzzyStringFind(citation,yearString)):
                    print("")
                    print("Tryied doi: " + doi)
                    print ("")
                    ask = raw_input('Could not find, title: "' + titleString.encode("UTF-8") + '" or year: "' + yearString.encode("UTF-8") + '" in\n\n' + citation.encode("UTF-8") + ", \n\nignore and take anyway (y/N): ")
                    if ask != "y":
                        if (len(altDois) != 0):
                            print("Ok ... I have " + str(len(altDois)) + " alternatives ..., continuing with next try")
                            doi = altDois[0]
                            altDois = altDois[1:]
                            print ("Will try " + doi + " next")
                            print ("Remaining dois:")
                            print altDois
                            try:
                                jsonData = getJsonForDoi(doi)
                                continue
                            except:
                                print("Error in getting doi ...")
                                errorDois.append((doi,citation))
                                break
                        else:
                            print("Storing as error ...")
                            errorDois.append((doi,citation))
                            break


            print "Final output"
            print fNamesString + fYearString + fTitleString+ fJournalString + fVolumeString + fPageString

            f = codecs.open(outputFile,"a","utf-8")
            s = (fNamesString + fYearString + fTitleString+ fJournalString + fVolumeString + fPageString)
            f.write(s + "\n\n")
            f.close()

            f = codecs.open(csvFile,"a", "utf-8")
            s = (doi + "\t" + namesString + "\t" + titleString + "\t" + journalString + "\t" + yearString + "\t" + volumeString + "\t" + pageString)
            f.write(s + "\n")
            f.close()
        except:
            print ("Error with: " + json.dumps(jsonData, sort_keys=True, indent=4, separators=(',', ': ')))
            e = sys.exc_info()[0]
            print ("Exception: %s" % e)
            print e.args
            errorDois.append((doi,citation))
        handled = True

print "Error dois:"
for e in errorDois:
    print e
print "Warning dois:"
for w in warningDois:
    print w
