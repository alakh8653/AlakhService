const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const AlakhService = require('../src/service');

describe('AlakhService', () => {
  test('starts with no items', () => {
    const svc = new AlakhService();
    assert.deepEqual(svc.getAll(), []);
  });

  test('creates an item with auto-incremented id', () => {
    const svc = new AlakhService();
    const item = svc.create({ name: 'foo' });
    assert.equal(item.id, 1);
    assert.equal(item.name, 'foo');
  });

  test('getById returns item when found', () => {
    const svc = new AlakhService();
    svc.create({ name: 'bar' });
    const item = svc.getById(1);
    assert.equal(item.name, 'bar');
  });

  test('getById returns null when not found', () => {
    const svc = new AlakhService();
    assert.equal(svc.getById(99), null);
  });

  test('updates an existing item', () => {
    const svc = new AlakhService();
    svc.create({ name: 'baz' });
    const updated = svc.update(1, { name: 'qux' });
    assert.equal(updated.name, 'qux');
    assert.equal(updated.id, 1);
  });

  test('update returns null for missing item', () => {
    const svc = new AlakhService();
    assert.equal(svc.update(99, { name: 'x' }), null);
  });

  test('deletes an existing item', () => {
    const svc = new AlakhService();
    svc.create({ name: 'del' });
    assert.equal(svc.delete(1), true);
    assert.deepEqual(svc.getAll(), []);
  });

  test('delete returns false for missing item', () => {
    const svc = new AlakhService();
    assert.equal(svc.delete(99), false);
  });

  test('getAll returns all items', () => {
    const svc = new AlakhService();
    svc.create({ name: 'a' });
    svc.create({ name: 'b' });
    assert.equal(svc.getAll().length, 2);
  });

  test('getAll returns a copy, not a reference', () => {
    const svc = new AlakhService();
    svc.create({ name: 'a' });
    const result = svc.getAll();
    result.push({ id: 99, name: 'injected' });
    assert.equal(svc.getAll().length, 1);
  });
});
