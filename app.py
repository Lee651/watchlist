import os
import sys
import click

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask import render_template
from flask import request, url_for, redirect, flash
# werkzeug.security.generate_password_hash() 用来为给定的密码生成密码散列值
# werkzeug.security.check_password_hash() 则用来检查给定的散列值和密码是否对应
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager
# 登录用户使用 Flask-Login 提供的 login_user() 函数实现
from flask_login import login_user, login_required, logout_user, current_user
from flask_login import UserMixin

WIN = sys.platform.startswith('win')
if WIN:  # 如果是 Windows 系统，使用三个斜线
    prefix = 'sqlite:///'
else:  # 否则使用四个斜线
    prefix = 'sqlite:////'

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = prefix + os.path.join(app.root_path, 'data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # 关闭对模型修改的监控
app.config['SECRET_KEY'] = 'dev'  # 等同于 app.secret_key = 'dev'

# 在扩展类实例化前加载配置
db = SQLAlchemy(app)
login_manager = LoginManager(app) 

# 注册这个函数的目的是，当程序运行后，
# 如果用户已登录， current_user 变量的值会是当前用户的用户模型类记录
@login_manager.user_loader
def load_user(user_id):  # 创建用户加载回调函数，接受用户 ID 作为参数
    user = User.query.get(int(user_id))  # 用 ID 作为 User 模型的主键查询对应的用户
    return user  # 返回用户对象

# 让存储用户的 User 模型类继承 Flask-Login 提供的 UserMixin 类, 可以很轻松的判断当前用户的认证状态
class User(db.Model, UserMixin):  # 表名将会是 user（自动生成，小写处理）   # 创建User模型类
    id = db.Column(db.Integer, primary_key=True)    # 主键
    name = db.Column(db.String(20))    # 名字
    username = db.Column(db.String(20))    # 用户名
    password_hash = db.Column(db.String(128))   # 密码散列值

    # 用来设置密码的方法，接受密码作为参数
    def set_password(self, password):
        # 将生成的密码保持到对应字段
        self.password_hash = generate_password_hash(password)

    # 用于验证密码的方法，接受密码作为参数
    def validate_password(self, password):
        # 返回布尔值
        return check_password_hash(self.password_hash, password)


class Movie(db.Model):      # 表名将会是 movie        # 创建Movie模型类
    id = db.Column(db.Integer, primary_key=True)    # 主键
    title = db.Column(db.String(60))      # 电影标题
    year = db.Column(db.String(4))    # 电影年份

login_manager.login_view = 'login'

@app.cli.command()
@click.option('--drop', is_flag=True, help='Create after drop.')
def initdb(drop):
    """Initialize the database."""
    if drop:
        db.drop_all()
    db.create_all()
    click.echo('Initialized database.')

@app.cli.command()   # 注册为命令
def forge():
    """Generate fake data."""
    db.create_all()

    # 全局的两个变量移动到这个函数内
    name = 'Grey Li'
    movies = [
        {'title': 'My Neighbor Totoro', 'year': '1988'},
        {'title': 'Dead Poets Society', 'year': '1989'},
        {'title': 'A Perfect World', 'year': '1993'},
        {'title': 'Leon', 'year': '1994'},
        {'title': 'Mahjong', 'year': '1996'},
        {'title': 'Swallowtail Butterfly', 'year': '1996'},
        {'title': 'King of Comedy', 'year': '1999'},
        {'title': 'Devils on the Doorstep', 'year': '1999'},
        {'title': 'WALL-E', 'year': '2008'},
        {'title': 'The Pork of Music', 'year': '2012'},
    ]

    user = User(name=name)
    db.session.add(user)     #将改动添加进数据库会话（一个临时区域）中
    for m in movies:
        movie = Movie(title=m['title'], year=m['year'])
        db.session.add(movie)

    db.session.commit()   # 提交数据库会话
    click.echo('Done.')


# 生成管理员账户
@app.cli.command()
# click.option() 装饰器设置的两个选项分别用来接受输入用户名和密码
@click.option('--username', prompt=True, help='The username used to login.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='The password used to login.')
def admin(username, password):
    """Create user."""
    db.create_all()

    user = User.query.first()
    if user is not None:
        click.echo('Updating user...')
        user.username = username
        user.set_password(password)  # 设置密码
    else:
        click.echo('Creating user...')
        user = User(username=username, name='Admin')
        user.set_password(password)  # 设置密码
        db.session.add(user)

    db.session.commit()  # 提交数据库会话
    click.echo('Done.')


@app.context_processor   # 模板上下文处理函数
# 这个函数返回的变量（以字典键值对的形式）将会统一注入到每一个模板的上下文环境中，因此可以直接在模板中使用
def inject_user():  # 函数名可以随意修改
    user = User.query.first()
    return dict(user=user)  # 需要返回字典，等同于 return {'user': user}

@app.route('/')
def index():
    movies = Movie.query.all()  # 读取所有电影记录    # 获取 Movie 模型的所有记录，返回包含多个模型类实例的列表
    return render_template('index.html', movies=movies)


@app.errorhandler(404)  # 传入要处理的错误代码
def page_not_found(e):  # 接受异常对象作为参数
    return render_template('404.html'), 404  # 返回模板和状态码

# 在 HTTP 中，GET 和 POST 是两种最常见的请求方法，其中 GET 请求用来获取资源，而 POST 则用来创建 / 更新资源
# 访问链接时会发送 GET 请求，而提交表单通常会发送 POST 请求
# 处理根地址请求的 indexs 视图函数默认只接受 GET 请求
# 为了能够处理 POST 请求，在 app.route() 装饰器里，用 methods 关键字传递一个包含 HTTP 方法字符串的列表
# 表示这个视图函数处理哪种方法类型的请求（下面的写法表示同时接受 GET 和 POST 请求）
@app.route('/', methods=['GET', 'POST'])  
def indexs():
    # 通过 request.method 的值来判断请求方法
    if request.method == 'POST':  
        # Flask-Login 提供了一个 current_user 变量，
        # 当程序运行后，如果用户已登录， current_user 变量的值会是当前用户的用户模型类记录
        # is_authenticated 属性：如果当前用户已经登录，那么 current_user.is_authenticated 会返回 True， 否则返回 False
        if not current_user.is_authenticated:  # 如果当前用户未认证
            return redirect(url_for('index'))  # 重定向到主页
        # 通过 request.form 来获取表单数据
        title = request.form.get('title')  # 传入表单对应输入字段的 name 值
        year = request.form.get('year')
        # 验证数据
        if not title or not year or len(year) > 4 or len(title) > 60:
            # flash() 函数用来在视图函数里向模板传递提示消息
            flash('Invalid input.')  # 显示错误提示
            return redirect(url_for('index'))  # 重定向回主页
        # 保存表单数据到数据库
        movie = Movie(title=title, year=year)  # 创建记录
        db.session.add(movie)  # 添加到数据库会话
        db.session.commit()  # 提交数据库会话
        flash('Item created.')  # 显示成功创建的提示
        return redirect(url_for('index'))  # 重定向回主页

    movies = Movie.query.all()
    return render_template('index.html', movies=movies)

# 编辑
# <int:movie_id> 部分表示 URL 变量，而 int 则是将变量转换成整型的 URL 变量转换器
@app.route('/movie/edit/<int:movie_id>', methods=['GET', 'POST'])
@login_required  # 登录保护
def edit(movie_id):
    # 使用 get_or_404() 方法，它会返回对应主键(movie_id 变量是电影条目记录在数据库中的主键值)的记录，
    # 如果没有找到，则返回 404 错误响应
    movie = Movie.query.get_or_404(movie_id)

    if request.method == 'POST':  # 处理编辑表单的提交请求
        title = request.form['title']
        year = request.form['year']

        if not title or not year or len(year) > 4 or len(title) > 60:
            flash('Invalid input.')
            return redirect(url_for('edit', movie_id=movie_id))  # 重定向回对应的编辑页面

        movie.title = title  # 更新标题
        movie.year = year  # 更新年份
        db.session.commit()  # 提交数据库会话
        flash('Item updated.')
        return redirect(url_for('index'))  # 重定向回主页

    return render_template('edit.html', movie=movie)  # 传入被编辑的电影记录


# 删除
@app.route('/movie/delete/<int:movie_id>', methods=['POST'])  # 限定只接受 POST 请求
@login_required  # 登录保护
def delete(movie_id):
    movie = Movie.query.get_or_404(movie_id)  # 获取电影记录
    db.session.delete(movie)  # 删除对应的记录
    db.session.commit()  # 提交数据库会话
    flash('Item deleted.')
    return redirect(url_for('index'))  # 重定向回主页


# 设置用户名字
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        name = request.form['name']

        if not name or len(name) > 20:
            flash('Invalid input.')
            return redirect(url_for('settings'))

        current_user.name = name
        # current_user 会返回当前登录用户的数据库记录对象
        # 等同于下面的用法
        # user = User.query.first()
        # user.name = name
        db.session.commit()
        flash('Settings updated.')
        return redirect(url_for('index'))

    return render_template('settings.html')


# 用户登录
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Invalid input.')
            return redirect(url_for('login'))

        # 查询并返回模型 User 类的第一条记录
        user = User.query.first()

        # 验证用户名和密码是否一致
        if username == user.username and user.validate_password(password):
            login_user(user)    # 登入用户
            flash('Login success.')
            return redirect(url_for('index'))  # 重定向到主页

        flash('Invalid username or password.')
        return redirect(url_for('login'))

    return render_template('login.html')


# 用户退出
@app.route('/logout')
@login_required   # 用于视图保护
def logout():
    logout_user()
    flash('Goodbye.')
    return redirect(url_for('index'))






