from pyspark import SparkConf, SparkContext
from pyspark.sql import HiveContext
import MySQLdb

conf = SparkConf().setAppName("sae_nginx_top_url")

sc = SparkContext(conf=conf)

hc = HiveContext(sc)


def mysqldb(host, port, user, passwd, db, sql):
    conn = None

    cur = None

    try:
        conn = MySQLdb.connect(host=host, port=port, user=user,
                               passwd=passwd, db=db, charset="utf8")

        cur = conn.cursor()

        cur.execute(sql)

        return cur.fetchall()
    except Exception, e:
        pass
    finally:
        if cur:
            try:
                cur.close()
            except Exception, e:
                pass

        if conn:
            try:
                conn.close()
            except Exception, e:
                pass

top_domain_list = mysqldb("m3353i.apollo.grid.sina.com.cn", 3353, "data_history", "f3u4w8n7b3h", "sae",
                          "select domain from (select domain,round(sum(flow)/1024/1024,0)  as flow_MB     from sae.sae_nginx_flow flow    where DATE_SUB(CURDATE(), INTERVAL 2 DAY) = date group by domain order by flow_MB desc limit 20)A")

top_domain_dict = {}

i = 1

for domain in top_domain_list:
    top_domain_dict[domain[0]] = i

    i = i + 1

print top_domain_dict

jsonRDD = hc.jsonFile(
    "/user/hdfs/rawlog/app_saesinacomkafka12345_nginx/2015_10_22/09")

hc.registerRDDAsTable(jsonRDD, "temp_schema")


def if_in_top_10_domain(domain):
    if domain == '' or domain == None or len(domain) < 3:
        return 'no'
    else:
        if top_domain_dict.has_key(domain):
            return top_domain_dict[domain]
        else:
            return 'no'

hc.registerFunction("temp_if_in_top_10_domain", if_in_top_10_domain)

spark_sql = '''select domain,domain_order,url,cast(sum(body_bytes_sent) as bigint) as flow,count(1) as num from (
                select domain,
                temp_if_in_top_10_domain(domain) as domain_order,
                split(request,'\\\\?')[0] as url,
                body_bytes_sent
                from temp_schema
                where body_bytes_sent>0 and temp_if_in_top_10_domain(domain)!='no'
                )A
           group by domain,domain_order,url
           order by flow desc limit 100
'''

rows_temp = hc.sql(spark_sql).map(lambda row: (
    (row.domain, row.domain_order, row.url, row.flow, row.num), None)).collect()

for val in rows_temp:
    print val

sc.stop()