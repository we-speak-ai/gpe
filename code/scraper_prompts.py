SYS_METADATA = """
Your job is to extract the author's name from an HTML web page and also the metadata tags like article category etc.
The following JSON output should be your output: 
{
    "author":  []"author name"], 
    "tags": [ "list of tags" ],
    "category": [ "list of categories" ]
}
Do not include any explanation only JSON
"""
SUMMARY_LENGHT = 500

SUMMARY_READ_TIME = 2

SYS_SUMMARY ="Your job is to create a shorter version of the given article around {word_count} character or {read_time} minute read time. Try to make it sound intresting. Do not include lines like: Here's a summary of the article in approximately 500 characters or a 2-minute read: etc! Keep the original language of the article. IF THE ARTICLE LANGUAGE WAS HUNGARIAN THEN YOUR OUTPUT ALSO MUST BE HUNGARIAN! You can use markdown formating.".format(word_count = SUMMARY_LENGHT, read_time=SUMMARY_READ_TIME)

SYS_HEADLINE = "Your job is to write a one sentence introduction or headline of the given text / article. This will be the headline of the articel. Do not include lines like: Here is a possible one-sentence introduction or headline for the article: etc! Keep the original language of the article. if it was Hungarian then your output should be hungarian! Dont use markdown formating, ONLY PLAIN TEXT!"