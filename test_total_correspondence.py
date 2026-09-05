from universal_field import canonical_field, self_procedure, correspondence_manifest, correspondence_verify, partition_field, reconstruct_parts

f=canonical_field(1.1975807343,"correspondence-test",sequential_nums=[1,2,3,5,8,13],feature_vector=[.25,.5,.75])
plan=self_procedure(f)
assert plan['field_id']==f['field_id'] and plan['invariant']
for n in (1,2,3,4,7,8,16,31,64,127):
    r=reconstruct_parts(partition_field(f,n))
    assert max(abs(float(f['coords'][k])-r[k]) for k in f['coords']) <= 1e-12
m=correspondence_manifest(f,{'event_id':'example'})
vr=correspondence_verify(f,m)
assert m['identity_correspondence'] and vr['pass'] and vr['max_projection_error']<=1e-12
bad={**m,'domains':{**m['domains'],'game':{**m['domains']['game'],'source_field_id':'tampered'}}}
assert not correspondence_verify(f,bad)['pass']
print('TOTAL CORRESPONDENCE PASS', f['field_id'], plan['part_counts'], plan['visual_projection_cover']['projection_count'])
