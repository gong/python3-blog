from aiohttp import web
#from app import get#循环导入导致AttributeError错误
from webutils import get,post
from mymodel import User,Blog,next_id,Comment,BlogTags
from apis import APIError,APIValueError,Page
import json
import hashlib
import re,time
from config import configs
import logging
logging.basicConfig(level=logging.INFO)
COOKIE_NAME = 'webappsession'
_COOKIE_KEY = configs.session.secret

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

# 解密cookie:

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

@get('/')
async def index(*,request):#为了实现web server 必须创建request handler 它可能是函数也可能是协程
    blogs = await Blog.findAll()
    blogtags=await BlogTags.findAll()
    return {
        '__template__': 'blogs.html',
        'blogs': blogs,
        'user': request.__user__,
        'blogtags':blogtags
    }
@get('/tag/{id}')
async def index2(*,id,request):
    blogs=await Blog.findAll(where="blogtag_id=?",args=[id])
    blogtags=await BlogTags.findAll()
    return {
        '__template__': 'blogs.html',
        'blogs': blogs,
        'user': request.__user__,
        'blogtags':blogtags
    }

@get('/api/comments')
def api_comments(*, page='1'):
    pass
@get('/blog/{id}')
async def get_blog(*,t=1,id,request):#如果t这里要有默认值，那直接放在request前面会报错，因为带有默认值得参数需要放在位置参数的后面，但是request需要放在所有参数的后面，所以这里在前面加一个*号
    logging.warning("打印：%s",t)
    blog=await Blog.find(id)
    comments=await Comment.findAll(where='blog_id=?',args=[id])
    if blog is not None:
        return {
            '__template__':'blog_view.html',
            'blog':blog,
            'user':request.__user__,
            'comments':comments
        }
    else:
        return {
            '__template__':'404.html'
        }
@get('/api/blog/{id}')
async def get_api_blog(id):
    blog=await Blog.find(id)
    blogtags=await BlogTags.findAll()
    blogtags=[dict(id=tag.id,name=tag.name) for tag in blogtags]
    return {
        'name':blog.name,
        'summary': blog.summary,
        'content': blog.content,
        'blogtags':blogtags,
        'tag':''
    }

@get('/signin')
async def signin():
    return {
        '__template__':'login.html'
    }

@get('/signout')
async def signout(request):
    # blogs = await Blog.findAll(where='user_id=?',args=[request.__user__.id])
    # r = web.Response()
    # r.del_cookie(COOKIE_NAME)
    # return r
    # return {
    #     '__template__': 'blogs.html',
    #     'blogs':blogs
    # }
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME,'-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    r.content_type = 'application/json'
    user=None
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    #r.location='/'
    return r
@get('/api/users')
def api_get_users(*,page=1,request):
    page_index=page
    num = yield from User.findNumber('count(id)')
    p = Page(num, int(page_index))
    if num == 0:
        return dict(page=p,users=())
    users = yield from User.findAll(orderBy='created_at desc',limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p,users=users)
@post('/api/users/{id}/delete')
async def delete_user(id):
    user=await User.find(id)
    if user is not None and user.admin is None:
        await user.remove()
    return '200'
@get('/manage/users/edit/{id}')
async def edit_user(id,request):
    user=await User.find(id)
    if user is not None:
        return {
            '__template__':'edit_user.html',
            'user2':user,
            'user':request.__user__
        }
    else:
        return '<script>alert("编辑的用户不存在");function(){vart = new Date().getTime(),url = location.pathname;if (location.search) {url = url + location.search + "&t=" + t;}else {url = url + "?t=" + t;}location.assign(url);}</script>'
@post('/manage/users/edit')
async def user_edit_save(passwd,id):
    user=await User.find(id)
    if user is not None:
        uid=next_id()
        sha1_passwd="%s:%s"%(uid,passwd)
        hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest()
        user.passwd=passwd
        await user.update()
    return '200'

@get('/manage/users')
def manage_users(*,page=1,request):
    if request.__user__ is not None:
        if request.__user__.admin:
            return {
                '__template__': 'manage_users.html',
                'page_index':page,
                'user': request.__user__
            }
        else:
            return '<script>alert("非法的访问");location.assign("/")</script>'
    else:
        return {
            '__template__':'login.html'
        }
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/users')
async def api_register_user(*, email, name, passwd):
    print('-------------------------------------------')
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        logging.warning("用户存在")
        raise APIError('register:failed', 'email', '邮箱已经被注册')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
@get('/register')
async def api_register():
    return {
        '__template__':'register.html'
    }

@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', '密码错误')
    if not passwd:
        raise APIValueError('passwd', '密码错误')
    users =await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', '邮箱不存在')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', '密码错误')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
@get('/api/blogs')
async def api_blogs(*, page=1):
    page_index = page
    num = await Blog.findNumber('count(id)')
    p = Page(num, int(page_index))
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc',limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)
@get('/manage/blogs')
def manage_blogs(*,page=1,request):
    if request.__user__ is not None:
        if request.__user__.admin:
            return {
                '__template__': 'manage_blogs.html',
                'page_index':page,
                'user':request.__user__
            }
        else:
            return '<script>alert("你没有权限进入");location.assign("/");</script>'
    else:
        return {
            '__template__':'login.html'
        }
@get('/manage/blogs/edit')
async def edit_blog(id,request):
    blog=await Blog.find(id)
    if blog is not None:
        return {
            '__template__':'edit_blog.html',
            'user':request.__user__,
            'id':id,
        }
    else:
        return '<script>alert("文章不存在已经丢失");location.assign("/")</script>'
@get('/manage/blogs/create')
async def create_blog(request):
    blogtags=await BlogTags.findAll()
    blogtags=[dict(id=tag.id,name=tag.name) for tag in blogtags]
    return {
        '__template__':'create_blog.html',
        'user':request.__user__,
        'blogtags':blogtags
    }
@post('/manage/blogs/edit')
async def blog_edit_save(*,id,tag,content,summary,name):
    blog=await Blog.find(id)
    if blog is not None:
        blog.summary=summary
        blog.content=content
        blog.name=name
        blog.blogtag_id=tag
        await blog.update()
    return '200'
@post('/api/blogs/{id}/delete')
async def delete_blog(id):
    blog=await Blog.find(id)
    if blog is not None:
        await blog.remove()
    return '200'
@post('/manage/blogs/create')
async def create_blog_save(content,tag,summary,name,request):
    id=next_id()
    user=request.__user__
    blog=Blog(id=id,content=content,summary=summary,name=name,user_name=user.name,user_image=user.image,user_id=user.id,blogtag_id=tag)
    await blog.save()
    return '200'
@post('/api/blogs/{id}/comments')
async def create_comment(id,content,request):
    blog=await Blog.find(id)
    if blog is not None:
        com=Comment(blog_id=id,user_id=request.__user__.id,user_image=request.__user__.image,user_name=request.__user__.name,content=content)
        await com.save()
    return '200'
@post('/api/comments/{id}/delete')
async def delete_comment(id):
    comment=await Comment.find(id)
    if comment is not None:
        await comment.remove()
    return '200'
@get('/manage/comments')
def manage_comments(*,page=1,request):
    if request.__user__ is not None:
        if request.__user__.admin:
            return {
                '__template__':'manage_comments.html',
                'user':request.__user__,
                'page_index':page
            }
        else:
            return '<script>alert("你没有权限进入");location.assign("/");</script>'
    else:
        return {
            '__template__': 'login.html'
        }
@get('/api/comments')
async def api_comments(*,page=1):
    page_index = page
    num = await Comment.findNumber('count(id)')
    p = Page(num, int(page_index))
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)
@get('/manage/blogtags')
def manage_blogtags(*,page=1,request):
    if request.__user__ is not None:
        if request.__user__.admin:
            return {
                '__template__':'manage_blogtags.html',
                'user':request.__user__,
                'page_index':page
            }
        else:
            return '<script>alert("你没有权限进入");location.assign("/");</script>'
    else:
        return {
            '__template__': 'login.html'
        }
@get('/api/blogtags')
async def api_blogtags(*,page=1):
    page_index=page
    num=await BlogTags.findNumber('count(id)')
    p=Page(num,int(page_index))
    if num==0:
        return dict(page=p,api_blogtags=())
    blogtags=await BlogTags.findAll(orderBy='created_at desc', limit=(p.offset,p.limit))
    return dict(page=p,blogtags=blogtags)
@get('/manage/blogtags/create')
async def create_blogtag(request):
    return {
        '__template__':'create_blogtag.html',
        'user':request.__user__
    }
@post('/manage/blogtags/create')
async def create_blogtag_save(name,remarks,request):
    id=next_id()
    blogtag=BlogTags(id=id,name=name,remarks=remarks)
    await blogtag.save()
    return '200'
@post('/api/blogtags/{id}/delete')
async def delete_blogtag(id):
    blogtag=await BlogTags.find(id)
    if blogtag is not None:
        await blogtag.remove()
    return '200'
@get('/manage/blogtags/edit/{id}')
async def edit_blogtag(id,request):
    blogtag=BlogTags.find(id)
    if blogtag is not None:
        return {
            '__template__':'edit_blogtag.html',
            'user':request.__user__,
            'id':id
        }
@get('/api/blogtag/{id}')
async def api_blogtag():
    blogtag=await BlogTags.find(id)
    return {
        'name':blogtag.name,
        'remarks':blogtag.remarks
    }
@post('/manage/blogtags/edit')
async def blogtag_edit_save(*,id,name,remarks):
    blogtag=await BlogTags.find(id)
    if blogtag is not None:
        blogtag.name=name,
        blogtag.remarks=remarks
        await blogtag.update()
    return '200'
