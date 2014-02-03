import webapp2

# returns the User object for the user. Otherwise None
from google.appengine.api import users

class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()

        # if signed in, display personalized message
        if user:
            self.response.headers['Content-Type'] = 'text/plain'
            self.response.out.write('Hello,' + user.nickname())
        # if not, redirect to the Google account sign-in screen
        # The redirect includes the URL to this page.
        # self.request.uri so the Google account sign-in mechanism
        # will send the user back after the user has signed in or
        # registered for a new account
        else:
            self.redirect(users.create_login_url(self.request.uri))

# Maps MainPage to root URL '/', when webapp2 receives an HTTP GET
# request to the URL /, it instantiates the MainPage class
# and calls the instances get method. Inside the method,
# info about the request is available using self.request.
# Typically the methode sets properties on self.response to
# prepare the response, then exits. webapp2 sends a response
# based on the final state of MainPage instance.
main = webapp2.WSGIApplication([('/', MainPage)],
                                debug=True)

# The app itself is represented by a webapp2.WSGIApplication instance
# The paramtere debug=true passed to its constructor tells webapp2
# to print stack traces to the browser output if a handler encounters
# an error or raises an exception. You may wish to remove this option
# from the final version of your application
