"Doto2 App as requested"
import datetime
import jinja2
import json
import logging
import os
import time
import webapp2
import gviz_api

from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from google.appengine.ext import db

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)


# "REQUEST PARAMETERS"
BASE_PATH = "http://api.steampowered.com/IDOTA2Match_570"
REQUEST_HANDLER_MATCHES = "GetMatchHistory/V001"
REQUEST_HANDLER_DETAILS = "GetMatchDetails/V001"
FORMAT = "json"
ACCESS_KEY = "868F9729F3F66210B13E1F69F3C48FCF"
URL_PATH_MATCHES = BASE_PATH + "/" + REQUEST_HANDLER_MATCHES + "/?format=" \
    + FORMAT + "&key=" + ACCESS_KEY + "&account_id="
URL_PATH_DETAILS = BASE_PATH + "/" + REQUEST_HANDLER_DETAILS + "/?format=" \
    + FORMAT + "&key=" + ACCESS_KEY + "&match_id="


class DotoPlayer(db.Model):
    """Docstring a what?"""
    user_id = db.StringProperty(required=True)
    match_history = db.TextProperty()


class Handler(webapp2.RequestHandler):
    "A general handler to inherit things from"
    def write(self, *a, **kw):
        "Write out stuff"
        self.response.out.write(*a, **kw)

    @classmethod
    def render_str(cls, template, *a, **params):
        "Returns rendered content"
        template = JINJA_ENV.get_template(template)
        return template.render(params)

    def render(self, template, *a, **params):
        "Render stuff"
        self.write(self.render_str(template, *a, **params))


class ResultHandler(Handler):
    """Docstring a what?"""
    @classmethod
    def get_score(cls, match_id, user_id):
        """
        Function: get_score(match_id)
            Given a match id, return whether a player won or lost the match.
            Relies on previously set global variables:
                URL_PATH_DETAILS - an url path ready for concatenation w
                                   ith a match id

        Parameters:
            match_id - an integer representing match ID
            user_id - a 64bit integer representing user ID

        Returns:
            Boolean value (True/False)

        See Also:
            get() method of MainPage
        """

        urlpath = URL_PATH_DETAILS + str(match_id)
        url = urlfetch.fetch(urlpath, method=urlfetch.GET, deadline=60)
        content = url.content
        result = json.loads(content)

        # """
        # To find which team player was on, we have to convert our 64bit int to
        # 32bit int (destructive of nature, so we do it only here) as it is
        # represented in the results fetched from the Valve Web API.
        # """
        for player in result['result']['players']:
            if player['account_id'] == int(user_id) & (0xffffffff):
                playerside = player['player_slot']

        # """ Playerside is a 8 bit integer with values 0-4 for radiant and
        #     129-133 for dire. """
        radiant_win = result['result']['radiant_win']

        # Rate-limiting ourselves to 1 request per second as Valve requested
        # The dude abides.
        # NOT
        # time.sleep(1)

        if radiant_win:
            if playerside < 5:
                return True
            else:
                return False
        else:
            if playerside > 5:
                return True
            else:
                return False

    def post(self):
        """Docstring a what?"""

        # Clear memcache
        memcache.flush_all()

        # Get user ID
        userid = self.request.get('userid')
        if not userid:
            logging.error("I GOT NO ID")
            self.redirect('/error')


        # Not sure if we gonna need this
        self.response.headers['Content-Type'] = 'application/json; \
                                                 charset=UTF-8'

        # Check if the player is in the database
        q = db.GqlQuery("SELECT * FROM DotoPlayer WHERE user_id=:u",
                        u=userid)
        player = q.get()


        # Setup for the first loop run
        last_match_time = time.time()
        matches_remaining = 1

        while matches_remaining > 0:

            logging.error("Matches remaining: %s" % matches_remaining)
            # Load the URL and store results into a result
            urlpath = URL_PATH_MATCHES + str(userid) + "&date_max=" + str(last_match_time)
            url = urlfetch.fetch(urlpath, method=urlfetch.GET,
                                 deadline=60)
            content = url.content
            result = json.loads(content)

            # Get a batch of matches and store them into a list called matches
            matches = []
            for match in result['result']['matches']:
                if match['lobby_type'] == 0:
                    matches.append([match['start_time'],
                                    self.get_score(match['match_id'], userid)])

            # If not a new player
            if player:
                # Get his match history
                history = json.loads(player.match_history)
                # For each match check if it is in history
                for match in matches:
                    # If not, add it to history
                    if match not in history:
                        history.append(match)
                player.match_history = json.dumps(history)
            # Otherwise create a new guy and save him to db
            else:
                player = DotoPlayer(user_id=userid,
                                    match_history=json.dumps(matches))
            player.put()

            # Get # of matches remaining
            matches_remaining = result['result']['results_remaining']

            # Get the time of the last match
            last_match_time = result['result']['matches'][-1]['start_time'] - 100

        # Sets memcache for 1h when done
        memcache.set('user%s' % player.user_id, player.match_history)


class MainPage(Handler):
    "Fetches data from Valve Web API and stores all in db and cache"
    def get(self):
        """A response to a GET request."""
        self.render("form.html")

    def post(self):
        """Docstring a what?"""
        # Get userid
        userid = self.request.get('userid')
        forced = self.request.get('forced')

        q = db.GqlQuery("SELECT * FROM DotoPlayer WHERE user_id=:u",
                        u=userid)
        player = q.get()

        if player and not forced:
            logging.error("Bouncing against memcache.")
            self.redirect('/getmatches?userid=%s' % userid)
        else:
            if player:
                player.match_history = json.dumps(list())
                player.put()
            taskqueue.add(url='/results', queue_name="matchresults",
                        params={'userid': userid, 'forced': forced})
            self.redirect('/wait?userid=%s' % userid)


class ErrorHandler(Handler):
    def get(self):
        self.write("Something went wrong. Nothing to see here, move on.")


class WaitingRoom(Handler):
    def get(self):
        status = self.request.get('status')
        userid = self.request.get('userid')
        self.render("wait.html", status=status, userid=userid)

    def post(self):
        userid = self.request.get('userid')
        results = memcache.get('user%s' % userid)
        if results:
            self.redirect("/visualize?userid=%s" % userid)
        else:
            self.redirect("/wait?userid=%s&status=notthereyet" % userid)


class GetMatches(Handler):
    def get(self):
        userid = self.request.get('userid')
        memc = memcache.get('user%s' % userid)
        if not memc:
            q = db.GqlQuery("SELECT * FROM DotoPlayer WHERE user_id=:u", u=userid)
            player = q.get()
            if player:
                memcache.set('user%s' % player.user_id, player.match_history)
            else:
                self.redirect('/error')
        self.redirect('/visualize?userid=%s' % userid)



class Visualize(Handler):
    def get(self):
        userid = self.request.get('userid')
        memc = memcache.get('user%s' % userid)
        stats = json.loads(memc)
        stats.sort(reverse=True)

        # Creating the data
        description = {"matchtime": ("number", "Match Time"),
                       "wins": ("number", "Wins"),
                       "losses": ("number", "Losses")
                       }

        data = [{"matchtime": i, "losses": 0, "wins": 0} for i in range(0, 24)]

        totalWins = 0
        totalLosses = 0

        for match in stats:
            bucket = int(time.strftime("%H", time.gmtime(match[0])))
            hasWon = match[1]
            if hasWon:
                data[bucket]['wins'] += 1
                totalWins += 1
            else:
                data[bucket]['losses'] += 1
                totalLosses += 1

        self.write("Total matches: %s   " % len(stats))
        self.write("Total wins: %s  " % totalWins)
        self.write("Total losses: %s    " % totalLosses)

        # data = []
        # for match in stats:
        #     data[time.strftime("%H:%M:%S", time.gmtime(match[0]))]



#
#         data = [{"matchtime": time.strftime("%H", time.gmtime(match[0])),
#                  "result": match[1]} for match in stats]
#
        # Loading it into gviz_api.DataTable
        data_table = gviz_api.DataTable(description)
        data_table.LoadData(data)

        # Creating a JavaScript code string
        jscode = data_table.ToJSCode("jscode_data",
                               columns_order=("matchtime", "wins", "losses"),
                               order_by="matchtime")

        # Creating a JSon string
        jsonz = data_table.ToJSon(columns_order=("matchtime", "wins", "losses"),
                           order_by="matchtime")

        self.render("chartsnstuff.html", json=jsonz)


APP = webapp2.WSGIApplication([
    ('/error', ErrorHandler),
    ('/results', ResultHandler),
    ('/wait', WaitingRoom),
    ('/getmatches', GetMatches),
    ('/visualize', Visualize),
    ('/.*', MainPage),
], debug=True)
