import praw
import time
import re
import json
import threading

#set globals

r=praw.Reddit('modmail')

#strings
SUBREDDIT_NAME="{}_mm"
SUBREDDIT_TITLE="Modmail Archive for /r/{}"



class Bot():

    def __init__(self):

        self.mappings=json.loads(r.subreddit('captainmeta4bots').wiki['archivist'].content_md)

    

    def invite_checker(self):
        
        #constant check for new mod invites
        for message in r.inbox.stream():

            message.mark_read()

            try:
                message.subreddit.mod.accept_invite()
            except:
                continue

            print('accepting mod invite to /r/{}'.format(message.subreddit.display_name))
            
            #check mapping to see if there's an existing archive sub
            if message.subreddit.display_name not in self.mappings:
                #create archiving sub
                name=SUBREDDIT_NAME.format(subreddit.display_name)
                title=SUBREDDIT_TITLE.format(subreddit.display_name)
                archive_subreddit=r.subreddit.create(name, title=title, link_type="self", subreddit_type="private")

                #update the mappings
                self.mappings[message.subreddit.display_name]=archive_subreddit.display_name
                r.subreddit('captainmeta4bots').wiki['archivist'].edit(json.dumps(self.mappings))
                               
            else:
                archive_subreddit=self.mappings[message.subreddit.display_name]


            #apply css
            css=open('CSS.txt').read()
            archive_subreddit.stylesheet.update(css,"Apply css")

            #apply AutoModerator config
            automod=open('AutoModerator.txt').read()
            archive_subreddit.wiki['config/AutoModerator'].edit(automod, "Apply AutoMod Config")

            #Add users
            for mod in message.subreddit.moderator(limit=None):
                if any(x in mod.mod_permissions for x in ['all','mail']):
                       archive_subreddit.contributor.add(mod)

    def update_contributors(self):

        #checks archive subreddits and cleans out contributors based on mod perms in corresponding subreddits


        pairs = {}

        moderated = list(x.display_name.lower() for x in r.user.moderator_subreddits(limit=None))

        #build list from sub pairs where both are modded
        for pair in self.mappings:
            if pair in moderated and self.mappings[pair] in moderated:
                pairs[pair]=self.mappings[pair]

        #now we check modded subs
        for pair in pairs:

            main=r.subreddit(pair)
            archive=r.subreddit(pairs[pair])

            #get list of people who should have access (and nobody else)
            mail_access=[]
            for mod in main.moderator():
                if any(x in mod.mod_permissions for x in ['all','mail']):
                    mail_access.append(mod.name)

            #get list of contributors
            contrib_list = list(x.name for x in archive.contributor(limit=None))

            #now we compare the two and add/remove as needed
            for name in contrib_list:
                if name not in mail_access:
                    archive.contributor.remove(name)
                    print('removed {} from {}'.format(name, archive.display_name))

            for name in mail_access:
                if name not in contrib_list:
                    archive.contributor.add(name)
                    print('added {} to {}'.format(name, archive.display_name))

    def access_lists(self):

        #process for keeping subreddit access lists up to date
        while True:
            self.update_contributors()
            time.sleep(3600)
                    
            

    def message_string(self, message):
        
        #Takes a singlemessage object and returns a markdown string to be used in the archive post
        

        #From - check distinguished status and append #mod or #admin to username link as needed - for CSS hooks
        #also check for [deleted]
        if message.author.is_subreddit_mod:
            archive_string = '[{}](/u/{}#mod)'.format(message.author.name, message.author.name)
        elif message.author.is_admin:
            archive_string = '[{}](/u/{}#admin)'.format(message.author.name, message.author.name)
        elif message.author.is_deleted:
            archive_string = '[deleted]'
        else:
            archive_string = '[{}](/u/{})'.format(message.author.name, message.author.name)
        

        #Timestamp
        t=time.strptime(message.date.split('.')[0],"%Y-%m-%dT%H:%M:%S")
        timestamp=time.strftime('%d %b %Y %H:%M:%S',t)
        archive_string = archive_string + ' at ' + timestamp + '\n\n'

        #Message contents
        archive_string = archive_string + message.body_markdown
        
        #Replace --- and ___ line seperators with ##--- or ##___ due to subreddit css
        archive_string = re.sub("\n\s*---+\s*\n","\n##---\n",archive_string)
        archive_string = re.sub("\n\s*___+\s*\n","\n##___\n",archive_string)

        return archive_string

    def conversation_url(self, conversation):
        #given conversation, return its url

        return "https://mod.reddit.com/mail/all/{}".format(conversation.id)

    def conversation_string(self, conversation):

        #takes a modmail conversation, converts it to postable text

        #first thing - link to modmail
        output = self.conversation_url(conversation)

        #now iterate through messages and add them
        for message in conversation.messages:

            output += "\n\n---\n\n"

            output += self.message_string(message)

        return output


    def archive_modmail(self):

        #get subs currently using New Modmail
        subs=list(r.subreddit('all').modmail.subreddits())

        #remove subs not found in mappings
        for sub in subs:
            if sub not in self.mappings:
                subs.remove(sub)

        #bulk read convos and archive

        for conversation in r.subreddit('captainmeta4bots').modmail.bulk_read(other_subreddits=subs):

            #mark read
            conversation.read()
            particpant = conversation.participant
            print('{} in /r/{}'.format(conversation.subject, conversation.owner.display_name))

            #check mapping and get subreddit
            if conversation.owner.display_name not in self.mappings:
                continue
            archive_subreddit=r.subreddit(self.mappings[conversation.owner.display_name])

            #generate archive text and title
            text=self.conversation_string(conversation)
            title=conversation.subject

            #search subreddit for id
            query="selftext:{}".format(conversation.id)
            for submission in archive_subreddit.search(query):
                if submission.selftext.startswith(self.conversation_url(conversation)):
                    submission.edit(text)
                    break
            else:
                #here we know (or at least think) no submission exists
                #we need to create one
                archive_subreddit.submit(title, selftext=text)

        

    def run(self):

        #spin invite monitor off as separate process
        invites = threading.Thread(target=self.invite_checker,name="invite monitor")
        invites.start()

        #spin off access list maintenance as separate process
        access = threading.Thread(target=self.access_lists, name="access maintenance")
        access.start()

        #archive modmail
        while True:
            self.archive_modmail()

if __name__=="__main__":
    b=Bot()
    b.run()

        
                
            
            
