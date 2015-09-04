import praw
import time
import re
import os

#set globals

##oauth stuff
client_id=os.environ.get('client_id')
client_secret=os.environ.get('client_secret')
redirect_uri='http://127.0.0.1:65010/authorize_callback'
state="Politics Modmail Archiver"


##account names
reader_account='politicsmoderatorbot'
poster_account='politics_mod_bot'

##reddit instances
user_agent=("Politics Modmail Archiver - /u/captainmeta4")
r=praw.Reddit(user_agent) #Allow for seamless switching between accounts
s=praw.Reddit(user_agent) #r is for captainmeta4. s is for politics_mod_bot
                          #Yes, they share a rate limit

#captainmeta4
#cap_refresh=os.environ.get('cap_refresh')

#politics_mod_bot
#bot_refresh=os.environ.get('bot_refresh')

#subreddits
read_subreddit = r.get_subreddit('politics')
archive_subreddit = r.get_subreddit('politics_modmail')


class Bot():

    def oauth_login(self):

        #r.set_oauth_app_info(client_id, client_secret, redirect_uri)
        #s.set_oauth_app_info(client_id, client_secret, redirect_uri)

        #r.refresh_access_information(cap_refresh)
        #s.refresh_access_information(bot_refresh)

        #print('refresh tokens used successfully')

        #Temporarily in place due to bug with praw where r.search does not work in private subreddits with OAuth
        s.login(poster_account,os.environ.get('bot_pass'))
        r.login(reader_account,os.environ.get('cap_pass'))
        print('logins successful')
        
    def message_string(self, message):
        #Takes a message object and returns a markdown string to be used in the archive post
        

        #From - check distinguished status and append #mod or #admin to username link as needed - for CSS hooks
        #also check for [deleted]
        if message.distinguished == 'moderator':
            archive_string = 'from ['+message.author.name+'](/u/'+message.author.name+'#mod) '
        elif message.distinguished == 'admin':
            archive_string = 'from ['+message.author.name+'](/u/'+message.author.name+'#admin) '
        elif message.author==None:
            archive_string = 'from [deleted] '
        else:
            archive_string = 'from ['+message.author.name+'](/u/'+message.author.name+') '

        #To
        archive_string = archive_string + 'to ' + message.dest
        

        #Timestamp
        timestamp = time.strftime("%a %b %d %Y %H:%M:%S GMT",time.gmtime(int(message.created_utc)))
        archive_string = archive_string + ' at ' + timestamp + '\n\n'

        #Message contents
        archive_string = archive_string + message.body
        
        #Replace --- line seperators with ##--- due to subreddit css
        archive_string = re.sub("\n---+\n","\n##---\n",archive_string)
        
        return archive_string
        

    def archive_modmail(self):

        for modmail in r.get_mod_mail(subreddit=read_subreddit, limit=1000):

            #Begin assembling text, starting with permalink
            archive_text = 'http://www.reddit.com/message/messages/'+modmail.id+'\n\n---\n\n'

            #First message
            archive_text = archive_text + self.message_string(modmail)

            #all reply message objects
            for reply in modmail.replies:
                archive_text = archive_text + '\n\n---\n\n' + self.message_string(reply)

            #Check and see if there's a submission for this thread already
            query = "author:politics_mod_bot self:yes selftext:"+modmail.id
            permalink = "http://www.reddit.com/message/messages/"+modmail.id

            for submission in s.search(query, subreddit=archive_subreddit,sort='new'):
                
                #Make sure search result isn't a false positive due to one thread being linked in another
                #since message permalink is first thing in archive text, this works
                
                if not submission.selftext.startswith(permalink):
                    continue

                #Check to see if nothing has changed, and if so, stop (because we're out of modmails to do since last cycle)
                if submission.selftext == archive_text:
                    print('all done for now')
                    return

                submission.edit(archive_text)
                print('submission edited')
                break
            
            else:
                #If there isn't an existing submission, make one and self-approve it
                s.submit(archive_subreddit, modmail.subject, text=archive_text).approve()
                print('new submission created')
                

if __name__=='__main__':
    modbot=Bot()
    while 1:
        print('running cycle')
        modbot.oauth_login()
        modbot.archive_modmail()
        print('sleeping for 30 min')
        time.sleep(1800)
