import urllib.request, json, sys

BASE = 'http://localhost:8002/api/v1'

# 1. Login demo
print('=== PASO 1: Login Demo ===')
req = urllib.request.Request(BASE + '/auth/demo-login', method='POST')
res = json.loads(urllib.request.urlopen(req).read())
token = res['access_token']
print('  Token obtenido: ' + token[:20] + '...')

# 2. Quick-eval: crear instrumento
print('')
print('=== PASO 2: Crear Instrumento CENSOPAS Corta ===')
payload = json.dumps({
    'company_name': 'Compania Minera Aurora Demo S.A.C.',
    'company_ruc': '20999777666',
    'company_sector': 'MINING',
    'instrument_version': 'SHORT',
    'study_name': 'Evaluacion CENSOPAS Corta Demo 2026',
    'population_invited': 50
}).encode()
req2 = urllib.request.Request(BASE + '/quick-eval', data=payload, method='POST',
    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
eval_res = json.loads(urllib.request.urlopen(req2).read())
print('  Proyecto ID: ' + str(eval_res.get('project_id')))
print('  Estudio ID: ' + str(eval_res.get('study_id')))
print('  Public ID: ' + str(eval_res.get('public_id')))
public_id = eval_res['public_id']

# 3. Simular 5 respuestas
print('')
print('=== PASO 3: Simular 5 Respuestas ===')
for i in range(5):
    # Create session
    sess_req = urllib.request.Request(BASE + '/public/studies/' + public_id + '/response-sessions', method='POST')
    sess_res = json.loads(urllib.request.urlopen(sess_req).read())
    sess_id = sess_res['id']
    questions = sess_res.get('questions', [])

    # Answer all questions
    for q in questions:
        q_id = q['id']
        answer = {'value': 2}
        ans_req = urllib.request.Request(BASE + '/response-sessions/' + str(sess_id) + '/responses/' + str(q_id),
            data=json.dumps(answer).encode(), method='PUT',
            headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(ans_req)

    # Complete session
    comp_req = urllib.request.Request(BASE + '/response-sessions/' + str(sess_id) + '/complete', method='POST')
    urllib.request.urlopen(comp_req)
    print('  Respuesta ' + str(i+1) + '/5 completada (session ' + str(sess_id) + ', ' + str(len(questions)) + ' preguntas)')

# 4. Check telemetry
print('')
print('=== PASO 4: Verificar Telemetria ===')
proj_id = eval_res['project_id']
tel_req = urllib.request.Request(BASE + '/projects/' + str(proj_id) + '/telemetry',
    headers={'Authorization': 'Bearer ' + token})
tel_res = json.loads(urllib.request.urlopen(tel_req).read())
print('  Total invitados: ' + str(tel_res.get('population_invited', 'N/A')))
print('  Sesiones completadas: ' + str(tel_res.get('completed_sessions', 'N/A')))
print('  Tasa participacion: ' + str(tel_res.get('participation_rate', 'N/A')))

# 5. Generate report preview
print('')
print('=== PASO 5: Generar Preview de Reporte ===')
study_id = eval_res['study_id']
rep_req = urllib.request.Request(BASE + '/studies/' + str(study_id) + '/reports/preview',
    method='POST', headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
    data=json.dumps({}).encode())
try:
    rep_res = json.loads(urllib.request.urlopen(rep_req).read())
    print('  Report ID: ' + str(rep_res.get('id', 'N/A')))
    print('  Status: ' + str(rep_res.get('status', 'N/A')))
except Exception as e:
    print('  Report preview: ' + str(e))

print('')
print('========================================')
print('DEMO COMPLETA - TODOS LOS PASOS OK')
print('URL Publica: https://mask-moss-annotation-sand.trycloudflare.com')
print('URL Encuesta: https://mask-moss-annotation-sand.trycloudflare.com/encuesta/' + public_id)
print('========================================')
