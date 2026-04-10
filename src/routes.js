const express = require('express');
const AlakhService = require('./service');

const router = express.Router();
const service = new AlakhService();

router.get('/items', (req, res) => {
  res.json(service.getAll());
});

router.get('/items/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) return res.status(400).json({ error: 'Invalid id' });
  const item = service.getById(id);
  if (!item) return res.status(404).json({ error: 'Item not found' });
  res.json(item);
});

router.post('/items', (req, res) => {
  const { name } = req.body || {};
  if (!name || typeof name !== 'string') {
    return res.status(400).json({ error: 'name is required' });
  }
  const item = service.create({ name });
  res.status(201).json(item);
});

router.put('/items/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) return res.status(400).json({ error: 'Invalid id' });
  const { name } = req.body || {};
  if (!name || typeof name !== 'string') {
    return res.status(400).json({ error: 'name is required' });
  }
  const item = service.update(id, { name });
  if (!item) return res.status(404).json({ error: 'Item not found' });
  res.json(item);
});

router.delete('/items/:id', (req, res) => {
  const id = parseInt(req.params.id, 10);
  if (isNaN(id)) return res.status(400).json({ error: 'Invalid id' });
  const deleted = service.delete(id);
  if (!deleted) return res.status(404).json({ error: 'Item not found' });
  res.status(204).send();
});

module.exports = router;
