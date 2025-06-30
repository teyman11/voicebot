import React, { useState, useEffect } from 'react';
import {
  Container,
  Tabs,
  Tab,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  IconButton,
  MenuItem,
  Typography,
  Alert,
  Snackbar,
  TablePagination,
  CircularProgress
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import axios from 'axios';
import { debounce } from 'lodash';

const API_URL = process.env.REACT_APP_API_URL;
const CATEGORIES = ['Appetizers', 'Main Course', 'Desserts', 'Beverages', 'Specials'];
const STATUSES = ['New', 'In Progress', 'Completed', 'Cancelled'];

function App() {
  const [tab, setTab] = useState(0);
  const [search, setSearch] = useState('');
  const [data, setData] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(5);
  const [loading, setLoading] = useState(false);

  const debouncedSetSearch = debounce((value) => setSearch(value), 300);

  useEffect(() => {
    fetchData();
  }, [tab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const endpoints = ['/api/menu-items', '/api/faqs', '/api/orders', '/api/reservations'];
      const response = await axios.get(`${API_URL}${endpoints[tab]}`);
      setData(response.data);
    } catch (error) {
      showSnackbar('Error fetching data', 'error');
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    if (tab === 0) {
      if (!form.name || !form.price || !form.category) {
        showSnackbar('Name, price, and category are required', 'error');
        return false;
      }
      if (form.price <= 0) {
        showSnackbar('Price must be greater than 0', 'error');
        return false;
      }
    } else if (tab === 1) {
      if (!form.question || !form.answer) {
        showSnackbar('Question and answer are required', 'error');
        return false;
      }
    } else if (tab === 2) {
      if (!form.phone || !form.items || !form.total) {
        showSnackbar('Phone, items, and total are required', 'error');
        return false;
      }
      if (form.total < 0) {
        showSnackbar('Total must be non-negative', 'error');
        return false;
      }
      if (typeof form.items === 'string' && !form.items.trim()) {
        showSnackbar('Items cannot be empty', 'error');
        return false;
      }
    } else if (tab === 3) {
      if (!form.phone || !form.date || !form.time || !form.party_size) {
        showSnackbar('Phone, date, time, and party size are required', 'error');
        return false;
      }
      try {
        new Date(form.date).toISOString();
      } catch {
        showSnackbar('Invalid date format. Use YYYY-MM-DD', 'error');
        return false;
      }
      if (!/^\d{2}:\d{2}$/.test(form.time)) {
        showSnackbar('Invalid time format. Use HH:MM', 'error');
        return false;
      }
      if (form.party_size <= 0 || form.party_size > 20) {
        showSnackbar('Party size must be between 1 and 20', 'error');
        return false;
      }
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    try {
      const endpoints = ['/api/menu-items', '/api/faqs', '/api/orders', '/api/reservations'];
      let formData = { ...form };

      if (tab === 0) {
        formData.price = Number(form.price);
      } else if (tab === 2) {
        formData.total = parseFloat(form.total);
        formData.items = typeof form.items === 'string'
          ? form.items.split(',').map(item => item.trim()).filter(item => item)
          : form.items;
        if (formData.items.length === 0) {
          showSnackbar('Items cannot be empty', 'error');
          return;
        }
      } else if (tab === 3) {
        formData.party_size = parseInt(form.party_size);
      }

      setLoading(true);
      if (editingId) {
        await axios.put(`${API_URL}${endpoints[tab]}/${editingId}`, formData);
        showSnackbar('Item updated successfully');
      } else {
        await axios.post(`${API_URL}${endpoints[tab]}`, formData);
        showSnackbar('Item added successfully');
      }
      fetchData();
      handleClose();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Error submitting form';
      showSnackbar(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    setLoading(true);
    try {
      const endpoints = ['/api/menu-items', '/api/faqs', '/api/orders', '/api/reservations'];
      await axios.delete(`${API_URL}${endpoints[tab]}/${id}`);
      showSnackbar('Item deleted successfully');
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'Error deleting item';
      showSnackbar(message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (item) => {
    setForm({
      ...item,
      items: tab === 2 ? (Array.isArray(item.items) ? item.items.join(', ') : item.items || '') : item.items
    });
    setEditingId(item.id);
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    setForm({});
    setEditingId(null);
  };

  const showSnackbar = (message, severity = 'success') => {
    setSnackbar({ open: true, message, severity });
  };

  const renderForm = () => {
    if (tab === 0) {
      return (
        <Stack spacing={2}>
          <TextField
            fullWidth
            label="Name"
            value={form.name || ''}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Price"
            type="number"
            value={form.price || ''}
            onChange={(e) => setForm({ ...form, price: e.target.value })}
            required
            inputProps={{ min: 0, step: 0.01 }}
          />
          <TextField
            fullWidth
            label="Description"
            value={form.description || ''}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <TextField
            select
            fullWidth
            label="Category"
            value={form.category || ''}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
            required
          >
            {CATEGORIES.map(category => (
              <MenuItem key={category} value={category}>{category}</MenuItem>
            ))}
          </TextField>
        </Stack>
      );
    } else if (tab === 1) {
      return (
        <Stack spacing={2}>
          <TextField
            fullWidth
            label="Question"
            value={form.question || ''}
            onChange={(e) => setForm({ ...form, question: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Answer"
            value={form.answer || ''}
            onChange={(e) => setForm({ ...form, answer: e.target.value })}
            required
          />
        </Stack>
      );
    } else if (tab === 2) {
      return (
        <Stack spacing={2}>
          <TextField
            fullWidth
            label="Name"
            value={form.name || ''}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextField
            fullWidth
            label="Phone"
            value={form.phone || ''}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Items (comma-separated)"
            value={form.items || ''}
            onChange={(e) => setForm({ ...form, items: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Total"
            type="number"
            value={form.total || ''}
            onChange={(e) => setForm({ ...form, total: e.target.value })}
            required
            inputProps={{ min: 0, step: 0.01 }}
          />
          <TextField
            fullWidth
            label="Special Instructions"
            value={form.special_instructions || ''}
            onChange={(e) => setForm({ ...form, special_instructions: e.target.value })}
          />
          <TextField
            select
            fullWidth
            label="Status"
            value={form.status || ''}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
          >
            {STATUSES.map(status => (
              <MenuItem key={status} value={status}>{status}</MenuItem>
            ))}
          </TextField>
        </Stack>
      );
    } else if (tab === 3) {
      return (
        <Stack spacing={2}>
          <TextField
            fullWidth
            label="Name"
            value={form.name || ''}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <TextField
            fullWidth
            label="Phone"
            value={form.phone || ''}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Date (YYYY-MM-DD)"
            value={form.date || ''}
            onChange={(e) => setForm({ ...form, date: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Time (HH:MM)"
            value={form.time || ''}
            onChange={(e) => setForm({ ...form, time: e.target.value })}
            required
          />
          <TextField
            fullWidth
            label="Party Size"
            type="number"
            value={form.party_size || ''}
            onChange={(e) => setForm({ ...form, party_size: e.target.value })}
            required
            inputProps={{ min: 1 }}
          />
          <TextField
            fullWidth
            label="Special Requests"
            value={form.special_requests || ''}
            onChange={(e) => setForm({ ...form, special_requests: e.target.value })}
          />
          <TextField
            select
            fullWidth
            label="Status"
            value={form.status || ''}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
          >
            {STATUSES.map(status => (
              <MenuItem key={status} value={status}>{status}</MenuItem>
            ))}
          </TextField>
        </Stack>
      );
    }
    return null;
  };

  const filteredData = data.filter(item => {
    if (tab === 0) {
      return (
        item.name?.toLowerCase().includes(search.toLowerCase()) ||
        item.description?.toLowerCase().includes(search.toLowerCase()) ||
        item.category?.toLowerCase().includes(search.toLowerCase())
      );
    } else if (tab === 1) {
      return (
        item.question?.toLowerCase().includes(search.toLowerCase()) ||
        item.answer?.toLowerCase().includes(search.toLowerCase())
      );
    } else if (tab === 2 || tab === 3) {
      return (
        String(item.phone || '').includes(search) ||
        item.name?.toLowerCase().includes(search.toLowerCase()) ||
        item.status?.toLowerCase().includes(search.toLowerCase())
      );
    }
    return true;
  });

  const paginatedData = filteredData.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const handleChangePage = (event, newPage) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const renderTable = () => {
    if (loading) {
      return <Typography align="center" sx={{ py: 4 }}><CircularProgress /></Typography>;
    }

    if (tab === 0) {
      return (
        <>
          <TextField
            fullWidth
            label="Search by name, description, or category"
            variant="outlined"
            sx={{ mb: 2 }}
            value={search}
            onChange={(e) => debouncedSetSearch(e.target.value)}
          />
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Price</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedData.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.name}</TableCell>
                  <TableCell>${Number(item.price).toFixed(2)}</TableCell>
                  <TableCell>{item.description}</TableCell>
                  <TableCell>{item.category}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => handleEdit(item)}><EditIcon /></IconButton>
                    <IconButton size="small" onClick={() => handleDelete(item.id)}><DeleteIcon /></IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={filteredData.length}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 20]}
          />
        </>
      );
    } else if (tab === 1) {
      return (
        <>
          <TextField
            fullWidth
            label="Search by question or answer"
            variant="outlined"
            sx={{ mb: 2 }}
            value={search}
            onChange={(e) => debouncedSetSearch(e.target.value)}
          />
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Question</TableCell>
                <TableCell>Answer</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedData.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{item.question}</TableCell>
                  <TableCell>{item.answer}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => handleEdit(item)}><EditIcon /></IconButton>
                    <IconButton size="small" onClick={() => handleDelete(item.id)}><DeleteIcon /></IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={filteredData.length}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 20]}
          />
        </>
      );
    } else if (tab === 2) {
      return (
        <>
          <TextField
            fullWidth
              label="Search by name, phone, or status"
              variant="outlined"
              sx={{ mb: 2 }}
              value={search}
              onChange={(e) => debouncedSetSearch(e.target.value)}
            />
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Time</TableCell>
                  <TableCell>Phone</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Items</TableCell>
                  <TableCell>Total</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {paginatedData.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{new Date(item.timestamp).toLocaleString()}</TableCell>
                    <TableCell>{item.phone}</TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>
                      {Array.isArray(item.items) ? item.items.join(', ') : item.items || 'No items'}
                    </TableCell>
                    <TableCell>${Number(item.total).toFixed(2)}</TableCell>
                    <TableCell>{item.status}</TableCell>
                    <TableCell>
                      <IconButton size="small" onClick={() => handleEdit(item)}><EditIcon /></IconButton>
                      <IconButton size="small" onClick={() => handleDelete(item.id)}><DeleteIcon /></IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <TablePagination
              component="div"
              count={filteredData.length}
              page={page}
              onPageChange={handleChangePage}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={handleChangeRowsPerPage}
              rowsPerPageOptions={[5, 10, 20]}
            />
          </>
        );
      } else if (tab === 3) {
      return (
        <>
          <TextField
            fullWidth
            label="Search by name, phone, or status"
            variant="outlined"
            sx={{ mb: 2 }}
            value={search}
            onChange={(e) => debouncedSetSearch(e.target.value)}
          />
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                <TableCell>Phone</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Date</TableCell>
                <TableCell>Time</TableCell>
                <TableCell>Party Size</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {paginatedData.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>{new Date(item.timestamp).toLocaleString()}</TableCell>
                  <TableCell>{item.phone}</TableCell>
                  <TableCell>{item.name}</TableCell>
                  <TableCell>{item.date}</TableCell>
                  <TableCell>{item.time}</TableCell>
                  <TableCell>{item.party_size}</TableCell>
                  <TableCell>{item.status}</TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => handleEdit(item)}><EditIcon /></IconButton>
                    <IconButton size="small" onClick={() => handleDelete(item.id)}><DeleteIcon /></IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={filteredData.length}
            page={page}
            onPageChange={handleChangePage}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={handleChangeRowsPerPage}
            rowsPerPageOptions={[5, 10, 20]}
          />
        </>
      );
    }
    return null;
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Paper sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(e, v) => setTab(v)} variant="fullWidth">
          <Tab label="Menu" />
          <Tab label="FAQs" />
          <Tab label="Orders" />
          <Tab label="Reservations" />
        </Tabs>
      </Paper>
      <Button variant="contained" sx={{ mb: 2 }} onClick={() => setOpen(true)}>
        Add {tab === 0 ? 'Menu Item' : tab === 1 ? 'FAQ' : tab === 2 ? 'Order' : 'Reservation'}
      </Button>
      <Paper>{renderTable()}</Paper>
      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>{editingId ? 'Edit' : 'Add'} {tab === 0 ? 'Menu Item' : tab === 1 ? 'FAQ' : tab === 2 ? 'Order' : 'Reservation'}</DialogTitle>
        <DialogContent>{renderForm()}</DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={loading}>
            {loading ? <CircularProgress size={24} /> : (editingId ? 'Update' : 'Add')}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={() => setSnackbar({ ...snackbar, open: false })}>
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Container>
  );
}

export default App;
