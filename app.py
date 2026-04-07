# app.py (updated with authentication)
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.utils
import json
import os
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

from config import GOOGLE_CONFIG, META_CONFIG, SECRET_KEY, DEBUG, MADISON_RED, MADISON_BLUE
from user_manager import get_user_manager

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# Initialize user manager
user_manager = get_user_manager()

# ============================================
# Authentication Decorator
# ============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        if not user_manager.is_admin(session['user_email']):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# Routes
# ============================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')
        
        user = user_manager.authenticate(email, password)
        
        if user:
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Main dashboard page"""
    return render_template('dashboard.html', 
                          user_name=session.get('user_name'),
                          user_email=session.get('user_email'),
                          is_admin=user_manager.is_admin(session.get('user_email', '')))

# ============================================
# Admin API Routes
# ============================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    """Get all users (admin only)"""
    users = user_manager.list_users()
    return jsonify({'users': users})

@app.route('/api/admin/users', methods=['POST'])
@admin_required
def create_user():
    """Create new user (admin only)"""
    data = request.json
    email = data.get('email', '').lower().strip()
    name = data.get('name', '')
    password = data.get('password', '')
    role = data.get('role', 'viewer')
    
    if not email or not name or not password:
        return jsonify({'success': False, 'error': 'Missing required fields'})
    
    success = user_manager.create_user(email, name, password, role)
    
    if success:
        return jsonify({'success': True, 'message': f'User {email} created successfully'})
    else:
        return jsonify({'success': False, 'error': 'User already exists'})

@app.route('/api/admin/users/<email>/toggle', methods=['POST'])
@admin_required
def toggle_user(email):
    """Toggle user active status (admin only)"""
    success = user_manager.toggle_user_status(email)
    return jsonify({'success': success})

@app.route('/api/admin/users/<email>', methods=['DELETE'])
@admin_required
def delete_user(email):
    """Delete user (admin only)"""
    success = user_manager.delete_user(email)
    return jsonify({'success': success})

# ============================================
# Google Ads Service Functions
# ============================================
def get_google_accessible_customers():
    """Get accessible Google Ads customers"""
    try:
        from google.ads.googleads.client import GoogleAdsClient
        
        client = GoogleAdsClient.load_from_dict(GOOGLE_CONFIG, version="v21")
        service = client.get_service("CustomerService")
        response = service.list_accessible_customers()
        return [x.split("/")[-1] for x in response.resource_names]
    except Exception as e:
        print(f"Error fetching Google customers: {e}")
        return []

def fetch_google_ads_data(customer_id, start_date, end_date):
    """Fetch Google Ads data"""
    try:
        from google.ads.googleads.client import GoogleAdsClient
        
        client = GoogleAdsClient.load_from_dict(GOOGLE_CONFIG, version="v21")
        ga_service = client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT
              campaign.name,
              ad_group.name,
              segments.date,
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros
            FROM ad_group
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
              AND metrics.impressions > 0
        """
        
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append({
                    "customer_id": customer_id,
                    "campaign_name": row.campaign.name,
                    "ad_group_name": row.ad_group.name,
                    "date": row.segments.date,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "cost": row.metrics.cost_micros / 1_000_000
                })
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error fetching Google data: {e}")
        return pd.DataFrame()

# ============================================
# Meta Ads Service Functions
# ============================================
def init_meta_api():
    """Initialize Meta Ads API"""
    try:
        from facebook_business.api import FacebookAdsApi
        FacebookAdsApi.init(
            META_CONFIG['app_id'], 
            META_CONFIG['app_secret'], 
            META_CONFIG['access_token'],
            api_version=META_CONFIG['api_version']
        )
        return True
    except Exception as e:
        print(f"Error initializing Meta API: {e}")
        return False

def get_meta_accessible_accounts():
    """Get accessible Meta Ads accounts"""
    try:
        from facebook_business.adobjects.user import User
        from facebook_business.adobjects.adaccount import AdAccount
        
        if not init_meta_api():
            return []
        
        me = User(fbid='me')
        ad_accounts = me.get_ad_accounts(fields=[AdAccount.Field.id, AdAccount.Field.name])
        
        accounts = []
        for account in ad_accounts:
            account_id = account.get_id()
            if not account_id.startswith('act_'):
                account_id = f"act_{account_id}"
            accounts.append({
                "id": account_id,
                "name": account.get('name', 'Unnamed Account')
            })
        return accounts
    except Exception as e:
        print(f"Error fetching Meta accounts: {e}")
        return []

def fetch_meta_ads_data(account_id, start_date, end_date):
    """Fetch Meta Ads data"""
    try:
        from facebook_business.adobjects.adaccount import AdAccount
        from facebook_business.adobjects.adsinsights import AdsInsights
        
        if not init_meta_api():
            return pd.DataFrame()
        
        if not account_id.startswith('act_'):
            account_id = f"act_{account_id}"
        
        account = AdAccount(account_id)
        
        fields = [
            AdsInsights.Field.campaign_name,
            AdsInsights.Field.adset_name,
            AdsInsights.Field.ad_name,
            AdsInsights.Field.date_start,
            AdsInsights.Field.impressions,
            AdsInsights.Field.clicks,
            AdsInsights.Field.spend
        ]
        
        params = {
            'level': 'ad',
            'time_range': {
                'since': start_date.strftime('%Y-%m-%d'),
                'until': end_date.strftime('%Y-%m-%d')
            },
            'limit': 500
        }
        
        insights = account.get_insights(fields=fields, params=params)
        rows = []
        for insight in insights:
            rows.append({
                "account_id": account_id,
                "campaign_name": insight.get('campaign_name', ''),
                "adset_name": insight.get('adset_name', ''),
                "ad_name": insight.get('ad_name', ''),
                "date": insight.get('date_start', ''),
                "impressions": float(insight.get('impressions', 0)),
                "clicks": float(insight.get('clicks', 0)),
                "spend": float(insight.get('spend', 0))
            })
        
        while insights.load_next_page():
            for insight in insights:
                rows.append({
                    "account_id": account_id,
                    "campaign_name": insight.get('campaign_name', ''),
                    "adset_name": insight.get('adset_name', ''),
                    "ad_name": insight.get('ad_name', ''),
                    "date": insight.get('date_start', ''),
                    "impressions": float(insight.get('impressions', 0)),
                    "clicks": float(insight.get('clicks', 0)),
                    "spend": float(insight.get('spend', 0))
                })
        
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error fetching Meta data: {e}")
        return pd.DataFrame()

# ============================================
# API Routes
# ============================================

@app.route('/api/accessible_accounts')
@login_required
def accessible_accounts():
    """Get accessible accounts for both platforms"""
    google_accounts = get_google_accessible_customers()
    meta_accounts = get_meta_accessible_accounts()
    
    return jsonify({
        'google_accounts': google_accounts,
        'meta_accounts': meta_accounts
    })

@app.route('/api/fetch_google', methods=['POST'])
@login_required
def fetch_google():
    """Fetch Google Ads data"""
    data = request.json
    customer_id = data.get('client_account') or data.get('manager_account')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not customer_id:
        return jsonify({'success': False, 'error': 'No account selected'})
    
    df = fetch_google_ads_data(customer_id, start_date, end_date)
    
    if df.empty:
        return jsonify({'success': False, 'error': 'No data found'})
    
    session['google_data'] = df.to_json()
    
    return jsonify({
        'success': True,
        'rows': len(df),
        'message': f'Loaded {len(df)} rows'
    })

@app.route('/api/fetch_meta', methods=['POST'])
@login_required
def fetch_meta():
    """Fetch Meta Ads data"""
    data = request.json
    account_id = data.get('account_id')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not account_id:
        return jsonify({'success': False, 'error': 'No account selected'})
    
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    df = fetch_meta_ads_data(account_id, start, end)
    
    if df.empty:
        return jsonify({'success': False, 'error': 'No data found'})
    
    session['meta_data'] = df.to_json()
    
    return jsonify({
        'success': True,
        'rows': len(df),
        'message': f'Loaded {len(df)} rows'
    })

@app.route('/api/dashboard_data')
@login_required
def dashboard_data():
    """Get dashboard data for charts"""
    google_json = session.get('google_data', '{}')
    meta_json = session.get('meta_data', '{}')
    
    try:
        google_df = pd.read_json(google_json) if google_json != '{}' else pd.DataFrame()
    except:
        google_df = pd.DataFrame()
    
    try:
        meta_df = pd.read_json(meta_json) if meta_json != '{}' else pd.DataFrame()
    except:
        meta_df = pd.DataFrame()
    
    # Calculate totals
    total_spend = 0
    total_clicks = 0
    total_impressions = 0
    
    if not google_df.empty:
        total_spend += google_df['cost'].sum() if 'cost' in google_df.columns else 0
        total_clicks += google_df['clicks'].sum() if 'clicks' in google_df.columns else 0
        total_impressions += google_df['impressions'].sum() if 'impressions' in google_df.columns else 0
    
    if not meta_df.empty:
        total_spend += meta_df['spend'].sum() if 'spend' in meta_df.columns else 0
        total_clicks += meta_df['clicks'].sum() if 'clicks' in meta_df.columns else 0
        total_impressions += meta_df['impressions'].sum() if 'impressions' in meta_df.columns else 0
    
    # Platform comparison chart
    platform_data = pd.DataFrame({
        'Platform': ['Google Ads', 'Meta Ads'],
        'Spend': [
            google_df['cost'].sum() if not google_df.empty and 'cost' in google_df.columns else 0,
            meta_df['spend'].sum() if not meta_df.empty and 'spend' in meta_df.columns else 0
        ]
    })
    
    fig_platform = px.bar(platform_data, x='Platform', y='Spend', 
                          title='Spend by Platform', color='Platform',
                          color_discrete_sequence=[MADISON_RED, MADISON_BLUE])
    
    # Trend chart
    trend_data = []
    if not google_df.empty and 'date' in google_df.columns:
        daily_google = google_df.groupby('date')['clicks'].sum().reset_index()
        daily_google['platform'] = 'Google Ads'
        trend_data.append(daily_google)
    
    if not meta_df.empty and 'date' in meta_df.columns:
        daily_meta = meta_df.groupby('date')['clicks'].sum().reset_index()
        daily_meta['platform'] = 'Meta Ads'
        trend_data.append(daily_meta)
    
    if trend_data:
        trend_df = pd.concat(trend_data, ignore_index=True)
        fig_trend = px.line(trend_df, x='date', y='clicks', color='platform',
                            title='Daily Clicks Trend', markers=True,
                            color_discrete_sequence=[MADISON_RED, MADISON_BLUE])
    else:
        fig_trend = px.line(title='No data available')
    
    # Google chart
    if not google_df.empty and 'date' in google_df.columns:
        google_daily = google_df.groupby('date')['clicks'].sum().reset_index()
        fig_google = px.line(google_daily, x='date', y='clicks',
                             title='Google Ads Performance', markers=True,
                             color_discrete_sequence=[MADISON_RED])
    else:
        fig_google = px.line(title='No Google Ads data available')
    
    # Meta chart
    if not meta_df.empty and 'date' in meta_df.columns:
        meta_daily = meta_df.groupby('date')['clicks'].sum().reset_index()
        fig_meta = px.line(meta_daily, x='date', y='clicks',
                           title='Meta Ads Performance', markers=True,
                           color_discrete_sequence=[MADISON_BLUE])
    else:
        fig_meta = px.line(title='No Meta Ads data available')
    
    return jsonify({
        'total_spend': float(total_spend),
        'total_clicks': int(total_clicks),
        'total_impressions': int(total_impressions),
        'total_ctr': (total_clicks / total_impressions * 100) if total_impressions > 0 else 0,
        'platform_chart': json.loads(json.dumps(fig_platform, cls=plotly.utils.PlotlyJSONEncoder)),
        'trend_chart': json.loads(json.dumps(fig_trend, cls=plotly.utils.PlotlyJSONEncoder)),
        'google_chart': json.loads(json.dumps(fig_google, cls=plotly.utils.PlotlyJSONEncoder)),
        'meta_chart': json.loads(json.dumps(fig_meta, cls=plotly.utils.PlotlyJSONEncoder))
    })

if __name__ == '__main__':
    # Create data directory if it doesn't exist
    Path("data").mkdir(exist_ok=True)
    app.run(debug=DEBUG, host='192.168.1.42', port=5000)
