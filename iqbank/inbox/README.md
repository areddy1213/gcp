# Inbox

Drop `.txt` or `.md` files here: one post or review per file. Subfolders are fine.
Everything in this folder except this README is git-ignored.

Use it for content iqbank deliberately doesn't crawl (Glassdoor, Blind, LeetCode Discuss):
copy the text while logged in as yourself and save it here.

Put the original URL on the first lines so the report links to it, and so the same post
reached another way counts as one source rather than two:

```
Source: https://www.glassdoor.com/Interview/...
Date: 2025-02

Interviewed for Security Engineer at Glean...
```

Edit a file and the next `iqbank collect` + `iqbank extract` re-extracts just that file.
