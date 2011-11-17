#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys
sys.path.append('/home/jerome/Sick-Beard')
import os
from sickbeard.name_parser import parser
import httplib
from httplib import InvalidURL
import urllib
from BeautifulSoup import BeautifulSoup
import re
from zipfile import ZipFile, BadZipfile

class subTitleGrabber:

    hostName = "www.tvsubtitles.net"

    def __init__(self, fileName, language):
        self.__fileName = fileName
        np = parser.NameParser(True)
        parsedFileName = str(np.parse(self.__fileName))
        fileNameParts = parsedFileName.split('-')
        self.__showName = "".join(fileNameParts[:1]).strip()
        self.__episodeString = "".join(fileNameParts[1:2]).strip()
        patternMatch = re.search("S([\d]+)E([\d]+)", self.__episodeString).groups()
        self.__seasonNb = patternMatch[0]
        self.__episodeNb = patternMatch[1]
        self.__HTTPHeaders = {
            "Content-type": "application/x-www-form-urlencoded",
            "User-Agent": "SickBeard",
            "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
            "Cookie": "visited=1; setlang=%s; visited1=1" % (language),
        }

    def fetchSubTitles(self):
        print("Fetching subtitles for %s" % (self.__fileName))
        self.sendSearchQuery()

    def sendSearchQuery(self):
        # http://www.tvsubtitles.net/search.php
        # **Phrase search** on the TV Show
        params = urllib.urlencode({'q': '"%s"' % (self.__showName)})

        response = self._sendHTTPRequest("POST", "/search.php", params)

        if( response.status == 200 ):
            data = response.read()
            self.findSeasonPage(data)

        return False

    def findSeasonPage(self, data):
        soup = BeautifulSoup(data)
        search = soup.findAll('ul', attrs={'style': 'margin-left:2em'})

        for base in search:
            # [:-5] removes the ".html" suffix
            showPage = base.find( "li" ).div.a['href'][:-5]

            seasonPage = "%s-%s.html" % (showPage, self.__seasonNb)

            response = self._sendHTTPRequest("GET", seasonPage)

            self.downloadSubtitle(response.read())

    def downloadSubtitle(self, data):
        episodeNb = self.__episodeNb
        if int(episodeNb) < 10:
            episodeNb = "0%s" % (episodeNb)

        soup = BeautifulSoup(data)
        base = soup.find('td', text="%sx%s" % (self.__seasonNb, episodeNb))

        if base is None:
            print("No subtitle found for this episode")
            return

        downloadPage = base.parent.findNextSibling('td').a['href']

        response = self._sendHTTPRequest("GET", "/%s" % (downloadPage))

        # What a pain !!
        soup = BeautifulSoup(response.read())
        div = soup.find('div', {'class': 'left_articles'})
        subtitleLinks = div.findAll('a', {'href':re.compile('/subtitle-([\d]+).html')})

        subtitleLink = self.findBestRated(subtitleLinks)

        if subtitleLink is None:
            print("No subtitle link found")
            return False

        downloadLink = subtitleLink['href'].replace('subtitle', 'download')

        response = self._sendHTTPRequest("GET", downloadLink)

        downloadableArchive = False
        if response.status == 302:
            for header in response.getheaders():
                if header[0] == 'location':
                    downloadableArchive = urllib.quote(header[1])
                    break

        if downloadableArchive is False:
            raise InvalidURL('No downloadable archive found')

        print("Downloading http://%s/%s" % (self.hostName, downloadableArchive))

        response = self._sendHTTPRequest("GET", "/"+downloadableArchive)
        data = response.read()

        archiveName = os.path.basename(downloadableArchive)
        fd = open(archiveName, 'wb')
        fd.write(data)
        fd.close()

        try:
            self.extractArchive(archiveName)
        except BadZipfile:
            print("Impossible to extract the archive : not a ZIP File")
        finally:
            os.remove(archiveName)

    def extractArchive(self, archiveName):
        zip = ZipFile(archiveName)
        for archiveMember in zip.infolist():
            if archiveMember.filename[-3:] == 'srt':
                targetName = "%s.srt" % (self.__fileName[:-4])
                print("Extracting %s to %s" % (archiveName, targetName))
                zip.extract(archiveMember)
                os.rename(archiveMember.filename, targetName)
                break

    def findBestRated(self, subtitleList):
        rating = 0
        bestSubtitle = None
        for subtitle in subtitleList:
            bad = float(subtitle.find('span', {'style':'color:red'}).string)
            good = float(subtitle.find('span', {'style':'color:green'}).string)
            downloadCount = int(
                subtitle.find('p', {'title':'downloaded'}).contents[1].strip())

            # not sure the formula is the good one
            try:
                current = ((bad/good + downloadCount * 2)/3)
            except ZeroDivisionError:
                current = downloadCount
            finally:
                if current > rating:
                    rating = current
                    bestSubtitle = subtitle


        return bestSubtitle

    def _sendHTTPRequest(self, method, page, params=''):
        conn = httplib.HTTPConnection(self.hostName)
        conn.request(method, page, params, self.__HTTPHeaders)
        response = conn.getresponse()
        return response

# Launch with python fr ./fetchsubtitles.py ./Bones.7x01.The.Memories.in.the.Shallow.Grave.avi
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide a path to an episode")
        exit(1)

    videoFile = sys.argv[2]
    language = sys.argv[1]
    grabber = subTitleGrabber(videoFile, language)
    grabber.fetchSubTitles()
