import asyncio
import logging
import aiomysql,sys
logging.basicConfig(level=logging.INFO)

@asyncio.coroutine
def create_pool(loop,**kw):#封装了aiomysql.create_pool函数
    logging.info('create database connect pool...')
    global __pools
    __pools=yield from aiomysql.create_pool(
        host=kw.get('host','localhost'),
        port=kw.get('port',3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset','utf8'),
        autocommit=kw.get('autocommit',True),
        maxsize=kw.get('maxsize',10),
        minsize=kw.get('minsize',1),
        loop=loop # 接收一个event_loop实例
    )
    logging.info("----------"if __pools is not None else "++++++++++++")
@asyncio.coroutine
def destroy_pool():
    global __pools
    if __pools is not None :
        __pools.close()  #关闭进程池,The method is not a coroutine,就是说close()不是一个协程，所以不用yield from
        yield from __pools.wait_closed() #但是wait_close()是一个协程，所以要用yield from,到底哪些函数是协程，上面Pool的链接中都有
@asyncio.coroutine
def select(sql,args,size=None):
    logging.info('sql:%s'%sql)
    logging.info('args:%s'%args)
    global __pools
    logging.info("----------" if __pools is not None else "++++++++++++")
    with (yield from __pools) as conn:
        cur=yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?','%s'),args or ())
        if size:
            rs=yield from cur.fetchmany(size)
        else:
            rs=yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows return: %s'% len(rs))
        return rs
@asyncio.coroutine
def execute(sql,args):#是insert update delete的通用执行函数
    logging.info('sql:%s'%sql)
    logging.info('args:%s'%args)
    with(yield from __pools) as conn:
        try:
            cur=yield from conn.cursor()
            yield from cur.execute(sql.replace('?','%s'),args)
            affected=cur.rowcount
            yield from cur.close()
        except BaseException as e:
            raise
        # finally:
        #     yield from conn.close()#释放数据库连接 会报错
        return affected
class Field(object):
    def __init__(self,name,column_type,primary_key,default):
        self.name=name
        self.column_type=column_type
        self.primary_key=primary_key
        self.default=default
    def __str__(self):
        return '<%s, %s:%s>'%(self.__class__.__name__,self.column_type,self.name)

class StringField(Field):#实现数据库中varchar类型到StringField的映射
    def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
        super().__init__(name,ddl,primary_key,default)

class IntegerField(Field):#实现数据库中int类型到IntegerField的映射
    def __init__(self,name=None,primary_key=False,default=0,ddl='int'):
        super().__init__(name,ddl,primary_key,default)
class FloatField(Field):
    def __init__(self,name=None,primary_key=False,default=0.0,ddl='real'):
        super().__init__(name,ddl,primary_key,default)
class BooleanField(Field):
    def __init__(self,name=None,default=None,ddl='boolean'):
        super().__init__(name,ddl,False,default)
class TextField(Field):
    def __init__(self,name=None,default=None,ddl='Text'):
        super().__init__(name,ddl,False,default)
class DateField(Field):
    def __init__(self,name=None,default=None,ddl='date'):
        super().__init__(name,ddl,False,default)

# 根据输入的参数生成占位符列表
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')

    # 以','为分隔符，将列表合成字符串
    return (','.join(L))


# -*-定义Model的元类

# 所有的元类都继承自type
# ModelMetaclass元类定义了所有Model基类(继承ModelMetaclass)的子类实现的操作

# -*-ModelMetaclass的工作主要是为一个数据库表映射成一个封装的类做准备：
# ***读取具体子类(user)的映射信息
# 创造类的时候，排除对Model类的修改
# 在当前类中查找所有的类属性(attrs)，如果找到Field属性，就将其保存到__mappings__的dict中，同时从类属性中删除Field(防止实例属性遮住类的同名属性)
# 将数据库表名保存到__table__中

# 完成这些工作就可以在Model中定义各种数据库的操作方法
class ModelMetaclass(type):
    # __new__控制__init__的执行，所以在其执行之前
    # cls:代表要__init__的类，此参数在实例化时由Python解释器自动提供(例如下文的User和Model)
    # bases：代表继承父类的集合
    # attrs：类的方法集合
    def __new__(cls, name, bases,attrs):
        #清除Model类本身
        if name=='Model':#元类的类的实例化时就会调用一次__new__ 而实际的类是继承Model当实际的类实例化时会调用父类则导致调用一次元类的__new__
            return type.__new__(cls,name,bases,attrs)
        #获取table名称
        tableName=attrs.get('__table__',None) or name
        logging.info('found model: %s(table:%s)'%(name,tableName))
        #获取所有的Field和主键名
        mappings=dict()
        fields=[]
        primaryKey=None
        for k,v in attrs.items():
            if isinstance(v,Field):
                logging.info('found map:%s===>%s'%(k,v))
                mappings[k]=v
                if v.primary_key:
                    #找到主键
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field :%s'%k)
                    primaryKey=k
                else:
                    fields.append(k)
        if not primaryKey:
            raise RuntimeError('Primary key not found')
        for k in mappings.keys():
            attrs.pop(k)
        escaped_fields=list(map(lambda f:'%s'%f,fields))
        attrs['__mappings__']=mappings#保存属性和列的映射关系
        attrs['__table__']=tableName
        attrs['__primary_key__']=primaryKey#主键属性名
        attrs['__fields__']=fields#除主键外的属性名
        # 构造默认的SELECT INSERT UPDATE DELETE 语句
        attrs['__select__']='select %s,%s from %s'%(primaryKey,','.join(escaped_fields),tableName)
        attrs['__insert__']='insert into %s (%s,%s)value(%s)'%(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
        attrs['__update__']='update %s set %s where %s=?'%(tableName,','.join(map(lambda f:'%s=?'%(mappings.get(f).name or f),fields)),primaryKey)
        attrs['__delete__']='delete from %s where %s=?'%(tableName,primaryKey)
        return type.__new__(cls,name,bases,attrs)

# Model继承dict 实现__getattr__ __setattr__方法
# 定义ORM所有映射的基类：Model
# Model类的任意子类可以映射一个数据库表
# Model类可以看作是对所有数据库表操作的基本定义的映射


# 基于字典查询形式
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
class Model(dict,metaclass=ModelMetaclass):
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)
    def __getattr__(self,key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has attribute '%s'"%key)
    def __setattr__(self, key, value):
        self[key]=value
    def getValue(self,key):
        return getattr(self,key,None)
    def getValueOrDefault(self,key):
        value=getattr(self,key,None)
        if value is None:
            field=self.__mappings__[key]
            if field.default is not None:
                value=field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s'%(key,str(value)))
                setattr(self,key,value)
        return value

    # 类方法有类变量cls传入，从而可以用cls做一些相关的处理。并且有子类继承时，调用该类方法时，传入的类变量cls是子类，而非父类。
    @classmethod
    @asyncio.coroutine
    def find(cls,pk):
        logging.info('find object by pk')
        rs=yield from select('%s where %s =?'%(cls.__select__,cls.__primary_key__),[pk],1)
        if len(rs)==0:
            return None
        else:
            return cls(**rs[0])#返回一条记录，以dict的形式返回，因为cls的父类继承了dict类

    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        '''find objects by where clause'''
        sql = [cls.__select__]

        if where:
            sql.append('where')
            sql.append(where)

        if args is None:
            args = []

        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)

        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        '''find number by select and where.'''
        sql = ['select %s __num__ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['__num__']

    @asyncio.coroutine
    def save(self):
        args=list(map(self.getValueOrDefault,self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        row=yield from execute(self.__insert__,args)
        if row!=1:
            logging.warning('failed to insert record affected rows:%s'%row)
    @asyncio.coroutine
    def update(self):
        args=list(map(self.getValueOrDefault,self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        row=yield from execute(self.__update__,args)
        if row!=1:
            logging.warning('failed to update record affected row :%s'%row)
    @asyncio.coroutine
    def remove(self):
        args=list(self.getValueOrDefault(self.__primary_key__))
        row=yield from execute(self.__delete__,args)
        if row!=1:
            logging.warning('failed to delete record affected rows:%s'%row)
if __name__ == '__main__':
    class User(Model):
        # 定义类的属性到列的映射：
        __table__='users'
        id = IntegerField('id', primary_key=True)
        username = StringField('username')
        email = StringField('email')
        password = StringField('password')
        birthday=DateField('birthday')
        nickname=StringField('nickname')
        # 创建一个实例：

    #创建异步事件句柄
    loop = asyncio.get_event_loop()
    @asyncio.coroutine
    def test():
        yield from create_pool(loop,password='1143178769',user='root',db='gong')
        #u = User(id='1235', username='peic', email='peic@python.org', password='password',birthday='1994-1-23',nickname='小黑')
        #yield from u.save()
        r=yield from User.find('1235')
        print(r)
        r2=yield from User.findAll()
        print(r2)
        yield from destroy_pool()#关闭pool
    loop.run_until_complete(test())
    loop.run_forever()
    if loop.is_closed():
        sys.exit(0)
