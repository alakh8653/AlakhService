class AlakhService {
  constructor() {
    this.items = [];
    this.nextId = 1;
  }

  getAll() {
    return [...this.items];
  }

  getById(id) {
    return this.items.find((item) => item.id === id) || null;
  }

  create(data) {
    const item = { id: this.nextId++, ...data };
    this.items.push(item);
    return item;
  }

  update(id, data) {
    const index = this.items.findIndex((item) => item.id === id);
    if (index === -1) return null;
    this.items[index] = { ...this.items[index], ...data, id };
    return this.items[index];
  }

  delete(id) {
    const index = this.items.findIndex((item) => item.id === id);
    if (index === -1) return false;
    this.items.splice(index, 1);
    return true;
  }
}

module.exports = AlakhService;
