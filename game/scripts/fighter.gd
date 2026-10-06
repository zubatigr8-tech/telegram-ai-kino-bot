class_name Fighter
extends Node3D
## Bitta jangchi: tana (oddiy shakllardan), harakat, zarbalar, himoya, qochish va nokaut.
## Boshqaruvchi (o'yinchi yoki bot) faqat move_input, set_block(), request_attack()
## va request_dodge() orqali buyruq beradi.

signal hit_landed(attacker: Fighter, target: Fighter, damage: float, kind: String)
signal knocked_out(fighter: Fighter)

enum State { IDLE, ATTACK, STAGGER, DODGE, KO }
enum Phase { WINDUP, STRIKE, RECOVERY }

## Zarbalar jadvali. Vaqtlar soniyada, masofa metrda.
const ATTACKS := {
	"jab":       {"damage": 4.0,  "stamina": 6.0,  "windup": 0.07, "active": 0.08, "recovery": 0.14, "range": 1.35, "block_mult": 0.15},
	"cross":     {"damage": 8.0,  "stamina": 10.0, "windup": 0.13, "active": 0.09, "recovery": 0.22, "range": 1.40, "block_mult": 0.20},
	"hook":      {"damage": 11.0, "stamina": 14.0, "windup": 0.17, "active": 0.10, "recovery": 0.28, "range": 1.20, "block_mult": 0.25},
	"uppercut":  {"damage": 13.0, "stamina": 16.0, "windup": 0.19, "active": 0.10, "recovery": 0.30, "range": 1.05, "block_mult": 0.30},
	"low_kick":  {"damage": 7.0,  "stamina": 12.0, "windup": 0.18, "active": 0.10, "recovery": 0.30, "range": 1.45, "block_mult": 0.60},
	"high_kick": {"damage": 16.0, "stamina": 22.0, "windup": 0.28, "active": 0.12, "recovery": 0.42, "range": 1.60, "block_mult": 0.30},
}

## Har bir zarba uchun pozalar: "wind" (tayyorlanish) va "strike" (urish). Burchaklar gradusda.
const POSES := {
	"jab": {
		"wind": {"spine": Vector3(0, 5, 0)},
		"strike": {"sh_l": Vector3(92, 0, 0), "el_l": Vector3(0, 0, 0), "spine": Vector3(-4, -12, 0)},
	},
	"cross": {
		"wind": {"spine": Vector3(0, -12, 0)},
		"strike": {"sh_r": Vector3(92, 0, 0), "el_r": Vector3(0, 0, 0), "spine": Vector3(-6, 28, 0)},
	},
	"hook": {
		"wind": {"sh_l": Vector3(80, 45, 0), "el_l": Vector3(70, 0, 0), "spine": Vector3(0, 15, 0)},
		"strike": {"sh_l": Vector3(85, -35, 0), "el_l": Vector3(65, 0, 0), "spine": Vector3(0, -35, 0)},
	},
	"uppercut": {
		"wind": {"sh_r": Vector3(15, 0, 0), "el_r": Vector3(115, 0, 0), "spine": Vector3(-12, 10, 0)},
		"strike": {"sh_r": Vector3(115, 0, 0), "el_r": Vector3(45, 0, 0), "spine": Vector3(8, 25, 0)},
	},
	"low_kick": {
		"wind": {"hip_r": Vector3(-20, 0, 0), "spine": Vector3(0, -15, 0)},
		"strike": {"hip_r": Vector3(55, 0, 25), "spine": Vector3(10, 20, 0)},
	},
	"high_kick": {
		"wind": {"hip_r": Vector3(-25, 0, 0), "spine": Vector3(5, -20, 0)},
		"strike": {"hip_r": Vector3(108, 0, 30), "hip_l": Vector3(-8, 0, 0), "spine": Vector3(25, 25, 0)},
	},
}

const GUARD := {
	"sh_l": Vector3(45, 0, -8), "el_l": Vector3(100, 0, 0),
	"sh_r": Vector3(45, 0, 8), "el_r": Vector3(100, 0, 0),
	"hip_l": Vector3(8, 0, -4), "hip_r": Vector3(-8, 0, 4),
	"spine": Vector3(-6, 0, 0),
}

const BLOCK := {
	"sh_l": Vector3(25, -10, -10), "el_l": Vector3(150, 0, 0),
	"sh_r": Vector3(25, 10, 10), "el_r": Vector3(150, 0, 0),
	"spine": Vector3(-14, 0, 0),
}

const JOINT_NAMES := ["sh_l", "el_l", "sh_r", "el_r", "hip_l", "hip_r", "spine"]
const PELVIS_HEIGHT := 0.95

@export var fighter_name := "Jangchi"
@export var skin_color := Color(0.87, 0.68, 0.53)
@export var shorts_color := Color(0.1, 0.3, 0.8)
@export var glove_color := Color(0.8, 0.1, 0.1)

# Xususiyatlar — keyinchalik mashg'ulot va karyera orqali oshiriladi.
var power := 1.0
var speed := 1.0
var endurance := 1.0

var max_health := 100.0
var health := 100.0
var max_stamina := 100.0
var stamina := 100.0

var opponent: Fighter
var ring_radius := 4.3
var can_act := false

## x: raqib tomon (+) / undan uzoqlashish (-), y: ekran ichiga (+) / tashqariga (-).
var move_input := Vector2.ZERO

var state: State = State.IDLE
var is_blocking := false
var current_attack := ""
var attack_phase: Phase = Phase.WINDUP
var attack_id := 0  # bot bir zarbaga bir marta reaksiya qilishi uchun

var _state_time := 0.0
var _hit_done := false
var _dodge_dir := Vector3.ZERO
var _knockback := Vector3.ZERO
var _queued_attack := ""
var _queued_time := 0.0
var _bob_time := 0.0
var _flash_time := 0.0
var _pose_tween: Tween
var _shown_block := false

var _joints := {}
var _pelvis: Node3D
var _body: Node3D
var _skin_mat: StandardMaterial3D


func _ready() -> void:
	_build_body()
	_apply_pose(GUARD, 0.0)


# ---------------------------------------------------------------------------
# Tana qurilishi
# ---------------------------------------------------------------------------

func _build_body() -> void:
	_skin_mat = _make_mat(skin_color)
	var shorts_mat := _make_mat(shorts_color)
	var glove_mat := _make_mat(glove_color)
	var dark_mat := _make_mat(Color(0.08, 0.08, 0.08))

	_body = Node3D.new()
	_body.name = "Body"
	add_child(_body)

	_pelvis = Node3D.new()
	_pelvis.position.y = PELVIS_HEIGHT
	_body.add_child(_pelvis)

	_add_mesh(_pelvis, _box(Vector3(0.42, 0.26, 0.26)), shorts_mat, Vector3(0, -0.02, 0))
	# Shortikdagi chiziq (keyin do'kondagi dizaynlar uchun joy)
	_add_mesh(_pelvis, _box(Vector3(0.43, 0.05, 0.27)), dark_mat, Vector3(0, 0.1, 0))

	for side in [-1, 1]:
		var hip := Node3D.new()
		hip.position = Vector3(0.12 * side, -0.05, 0)
		_pelvis.add_child(hip)
		_add_mesh(hip, _capsule(0.085, 0.5), shorts_mat, Vector3(0, -0.2, 0))  # shortik oyog'i
		_add_mesh(hip, _capsule(0.075, 0.9), _skin_mat, Vector3(0, -0.45, 0))
		_add_mesh(hip, _box(Vector3(0.12, 0.07, 0.24)), _skin_mat, Vector3(0, -0.88, -0.05))
		_joints["hip_l" if side < 0 else "hip_r"] = hip

	var spine := Node3D.new()
	spine.position.y = 0.08
	_pelvis.add_child(spine)
	_joints["spine"] = spine

	_add_mesh(spine, _capsule(0.2, 0.62), _skin_mat, Vector3(0, 0.3, 0), Vector3(1.25, 1, 0.75))
	_add_mesh(spine, _capsule(0.06, 0.14), _skin_mat, Vector3(0, 0.66, 0))  # bo'yin
	var head := _add_mesh(spine, _sphere(0.13), _skin_mat, Vector3(0, 0.8, 0))
	head.scale = Vector3(0.95, 1.1, 1.0)
	_add_mesh(spine, _sphere(0.135), dark_mat, Vector3(0, 0.84, 0.02), Vector3(1, 0.75, 1))  # soch

	for side in [-1, 1]:
		var sh := Node3D.new()
		sh.position = Vector3(0.27 * side, 0.52, 0)
		spine.add_child(sh)
		_add_mesh(sh, _capsule(0.06, 0.34), _skin_mat, Vector3(0, -0.15, 0))
		var el := Node3D.new()
		el.position.y = -0.3
		sh.add_child(el)
		_add_mesh(el, _capsule(0.052, 0.3), _skin_mat, Vector3(0, -0.13, 0))
		_add_mesh(el, _sphere(0.09), glove_mat, Vector3(0, -0.3, 0), Vector3(1, 1.1, 1.15))
		_add_mesh(el, _capsule(0.06, 0.12), glove_mat, Vector3(0, -0.21, 0))  # qo'lqop bilagi
		var suffix := "_l" if side < 0 else "_r"
		_joints["sh" + suffix] = sh
		_joints["el" + suffix] = el


func _make_mat(c: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.7
	return m


func _add_mesh(parent: Node3D, mesh: Mesh, mat: Material, pos: Vector3, scl := Vector3.ONE) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = pos
	mi.scale = scl
	parent.add_child(mi)
	return mi


func _box(size: Vector3) -> BoxMesh:
	var b := BoxMesh.new()
	b.size = size
	return b


func _capsule(r: float, h: float) -> CapsuleMesh:
	var c := CapsuleMesh.new()
	c.radius = r
	c.height = h
	c.radial_segments = 12
	c.rings = 4
	return c


func _sphere(r: float) -> SphereMesh:
	var s := SphereMesh.new()
	s.radius = r
	s.height = r * 2.0
	s.radial_segments = 16
	s.rings = 8
	return s


# ---------------------------------------------------------------------------
# Pozalar
# ---------------------------------------------------------------------------

func _apply_pose(pose: Dictionary, time: float) -> void:
	if _pose_tween:
		_pose_tween.kill()
	var target := GUARD.duplicate()
	for k in pose:
		target[k] = pose[k]
	if time <= 0.0:
		for j in JOINT_NAMES:
			(_joints[j] as Node3D).rotation_degrees = target[j]
		return
	_pose_tween = create_tween().set_parallel(true).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	for j in JOINT_NAMES:
		_pose_tween.tween_property(_joints[j], "rotation_degrees", target[j], time)


func _rest_pose() -> Dictionary:
	return BLOCK if is_blocking else GUARD


# ---------------------------------------------------------------------------
# Boshqaruvchi uchun buyruqlar
# ---------------------------------------------------------------------------

func request_attack(attack: String) -> void:
	if not ATTACKS.has(attack):
		return
	if state == State.IDLE and can_act:
		_start_attack(attack)
	elif state != State.KO:
		# Zarba tugashiga oz qolganda bosilsa, navbatga qo'yamiz (kombo uchun).
		_queued_attack = attack
		_queued_time = 0.3


func set_block(on: bool) -> void:
	is_blocking = on and can_act and state != State.KO


func request_dodge() -> void:
	if state != State.IDLE or not can_act or stamina < 12.0 or opponent == null:
		return
	stamina -= 14.0
	state = State.DODGE
	_state_time = 0.0
	var away := (global_position - opponent.global_position)
	away.y = 0
	away = away.normalized()
	var side := Vector3.UP.cross(away) * (1.0 if randf() < 0.5 else -1.0)
	var dir := move_input
	if dir.length() > 0.3:
		_dodge_dir = (_axis_toward() * dir.x + _axis_side() * dir.y).normalized()
	else:
		_dodge_dir = (away * 0.6 + side * 0.8).normalized()
	_apply_pose({"spine": Vector3(-25, 0, 15)}, 0.1)


func is_in_windup() -> bool:
	return state == State.ATTACK and attack_phase == Phase.WINDUP


func reset_for_round(pos: Vector3, heal: float) -> void:
	global_position = pos
	state = State.IDLE
	is_blocking = false
	current_attack = ""
	_queued_attack = ""
	_knockback = Vector3.ZERO
	health = min(max_health, health + heal)
	stamina = max_stamina
	_body.rotation = Vector3.ZERO
	_body.position = Vector3.ZERO
	_apply_pose(GUARD, 0.0)


# ---------------------------------------------------------------------------
# Asosiy sikl
# ---------------------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if opponent == null:
		return
	_state_time += delta
	_queued_time -= delta
	_update_flash(delta)

	match state:
		State.ATTACK:
			_update_attack()
		State.STAGGER:
			if _state_time > 0.32:
				_to_idle()
		State.DODGE:
			var t := _state_time / 0.32
			global_position += _dodge_dir * 5.5 * (1.0 - t) * delta
			if _state_time > 0.32:
				_to_idle()
		State.KO:
			return

	if state == State.IDLE and _queued_attack != "" and _queued_time > 0.0 and can_act:
		var a := _queued_attack
		_queued_attack = ""
		_start_attack(a)

	_update_movement(delta)
	_update_stamina(delta)
	_face_opponent()

	# Blok pozasini faqat holat o'zgarganda yangilaymiz.
	if state == State.IDLE and is_blocking != _shown_block:
		_shown_block = is_blocking
		_apply_pose(_rest_pose(), 0.1)

	# Nafas olish / tebranish
	_bob_time += delta * (6.0 if move_input.length() > 0.1 else 3.0)
	_pelvis.position.y = PELVIS_HEIGHT + sin(_bob_time) * 0.015


func _update_movement(delta: float) -> void:
	var spd := 2.3 * speed
	if is_blocking:
		spd *= 0.45
	if state == State.ATTACK:
		spd *= 0.25
	elif state != State.IDLE:
		spd = 0.0
	if not can_act:
		spd = 0.0
	var mv := move_input.limit_length(1.0)
	var vel := _axis_toward() * mv.x + _axis_side() * mv.y
	global_position += vel * spd * delta

	global_position += _knockback * delta
	_knockback = _knockback.move_toward(Vector3.ZERO, 12.0 * delta)

	# Raqib bilan ichma-ich kirib qolmaslik
	var diff := global_position - opponent.global_position
	diff.y = 0
	var d := diff.length()
	if d < 0.8 and d > 0.001:
		global_position += diff / d * (0.8 - d) * 0.5

	# Ring ichida qolish
	var flat := Vector2(global_position.x, global_position.z)
	if flat.length() > ring_radius:
		flat = flat.normalized() * ring_radius
		global_position.x = flat.x
		global_position.z = flat.y
	global_position.y = 0.0


func _update_stamina(delta: float) -> void:
	var regen := 13.0 * endurance
	if is_blocking:
		regen *= 0.4
	if state == State.ATTACK:
		regen = 0.0
	if move_input.length() > 0.1:
		regen *= 0.75
	stamina = clamp(stamina + regen * delta, 0.0, max_stamina)


func _face_opponent() -> void:
	var target := opponent.global_position
	target.y = global_position.y
	if target.distance_to(global_position) > 0.01:
		look_at(target, Vector3.UP)


func _axis_toward() -> Vector3:
	var d := opponent.global_position - global_position
	d.y = 0
	return d.normalized() if d.length() > 0.001 else Vector3.FORWARD


func _axis_side() -> Vector3:
	# Kamera qarash yo'nalishi bilan bir xil — "ekran ichiga".
	return Vector3.UP.cross(_axis_toward())


func distance_to_opponent() -> float:
	var d := opponent.global_position - global_position
	d.y = 0
	return d.length()


# ---------------------------------------------------------------------------
# Zarba
# ---------------------------------------------------------------------------

func _start_attack(attack: String) -> void:
	var a: Dictionary = ATTACKS[attack]
	if stamina < float(a["stamina"]) * 0.5:
		return
	stamina = max(0.0, stamina - float(a["stamina"]))
	state = State.ATTACK
	current_attack = attack
	attack_phase = Phase.WINDUP
	attack_id += 1
	_state_time = 0.0
	_hit_done = false
	_apply_pose(POSES[attack]["wind"], float(a["windup"]) / speed)


func _update_attack() -> void:
	var a: Dictionary = ATTACKS[current_attack]
	var windup := float(a["windup"]) / speed
	var active := float(a["active"]) / speed
	var recovery := float(a["recovery"]) / speed
	if attack_phase == Phase.WINDUP and _state_time >= windup:
		attack_phase = Phase.STRIKE
		_apply_pose(POSES[current_attack]["strike"], active * 0.7)
	if attack_phase == Phase.STRIKE and not _hit_done and _state_time >= windup + active * 0.6:
		_hit_done = true
		_resolve_hit(a)
	if attack_phase == Phase.STRIKE and _state_time >= windup + active:
		attack_phase = Phase.RECOVERY
		_apply_pose(_rest_pose(), recovery)
	if attack_phase == Phase.RECOVERY and _state_time >= windup + active + recovery:
		_to_idle()


func _resolve_hit(a: Dictionary) -> void:
	if opponent.state == State.KO:
		return
	if distance_to_opponent() > float(a["range"]):
		return
	# Charchaganda zarba kuchsizlanadi.
	var tired := 0.55 + 0.45 * (stamina / max_stamina)
	var dmg := float(a["damage"]) * power * tired * randf_range(0.9, 1.1)
	opponent.receive_hit(self, current_attack, dmg, float(a["block_mult"]))


func receive_hit(attacker: Fighter, attack: String, dmg: float, block_mult: float) -> void:
	if state == State.KO:
		return
	if state == State.DODGE and _state_time < 0.25:
		hit_landed.emit(attacker, self, 0.0, "dodge")
		return

	var kind := "hit"
	if is_blocking and state == State.IDLE:
		dmg *= block_mult
		stamina -= dmg * 2.5 + 3.0
		kind = "block"
		if stamina <= 0.0:
			stamina = 0.0
			kind = "guard_break"
			_stagger(attacker, 0.6)
	else:
		if state == State.ATTACK and attack_phase == Phase.WINDUP:
			dmg *= 1.35  # kontr-zarba
			kind = "counter"
		_stagger(attacker, 1.0)
		if attack == "low_kick":
			stamina = max(0.0, stamina - 8.0)

	health = max(0.0, health - dmg)
	_flash_time = 0.12
	hit_landed.emit(attacker, self, dmg, kind)
	if health <= 0.0:
		_knock_out()


func _stagger(attacker: Fighter, strength: float) -> void:
	state = State.STAGGER
	_state_time = 0.0
	current_attack = ""
	is_blocking = false
	_shown_block = false
	var push := global_position - attacker.global_position
	push.y = 0
	_knockback = push.normalized() * 2.2 * strength
	_apply_pose({"spine": Vector3(18, randf_range(-20, 20), randf_range(-10, 10))}, 0.06)


func _knock_out() -> void:
	state = State.KO
	can_act = false
	is_blocking = false
	if _pose_tween:
		_pose_tween.kill()
	var t := create_tween().set_parallel(true)
	t.tween_property(_body, "rotation_degrees:x", 88.0, 0.7).set_trans(Tween.TRANS_BOUNCE).set_ease(Tween.EASE_OUT)
	t.tween_property(_body, "position:y", 0.12, 0.7)
	t.tween_property(_joints["sh_l"], "rotation_degrees", Vector3(160, 0, -40), 0.5)
	t.tween_property(_joints["sh_r"], "rotation_degrees", Vector3(160, 0, 40), 0.5)
	t.tween_property(_joints["el_l"], "rotation_degrees", Vector3(10, 0, 0), 0.5)
	t.tween_property(_joints["el_r"], "rotation_degrees", Vector3(10, 0, 0), 0.5)
	knocked_out.emit(self)


func _to_idle() -> void:
	state = State.IDLE
	current_attack = ""
	_state_time = 0.0
	_shown_block = is_blocking
	_apply_pose(_rest_pose(), 0.12)


func _update_flash(delta: float) -> void:
	if _flash_time > 0.0:
		_flash_time -= delta
		_skin_mat.albedo_color = skin_color.lerp(Color(1, 0.3, 0.3), 0.6)
		if _flash_time <= 0.0:
			_skin_mat.albedo_color = skin_color
