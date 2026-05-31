'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useProducts, useCreateProduct, useUpdateProduct, useDeleteProduct } from '@/services/api/products';
import { ProductTable } from '@/components/products/ProductTable';
import { ProductCard } from '@/components/products/ProductCard';
import { ProductFormModal } from '@/components/products/ProductFormModal';
import { Product } from '@/types/product';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Plus, Grid, List, ChevronLeft, ChevronRight, Filter, RefreshCw, AlertCircle, Package } from 'lucide-react';
import { debounce, throttle } from 'lodash';
import { toast } from 'sonner';

export default function ProductsPage() {
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');
  
  // Filter States
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [throttledSearch, setThrottledSearch] = useState('');
  
  const [stockStatus, setStockStatus] = useState<'all' | 'in_stock' | 'out_of_stock'>('all');
  const [isActive, setIsActive] = useState<'all' | 'active' | 'inactive'>('all');
  
  // Cursor Pagination States
  const [cursor, setCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([null]);
  
  // Modal States
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Zod validation handler inputs
  const createProductMutation = useCreateProduct();
  const updateProductMutation = useUpdateProduct();
  const deleteProductMutation = useDeleteProduct();

  // Lodash Debouncing to limit search API triggers
  const debouncedSearchFn = useMemo(
    () =>
      debounce((val: string) => {
        setDebouncedSearch(val);
      }, 400),
    []
  );

  // Lodash Throttling to update immediate UI components or analytics if needed
  const throttledSearchFn = useMemo(
    () =>
      throttle((val: string) => {
        setThrottledSearch(val);
      }, 600),
    []
  );

  // Handle search input changes
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchInput(val);
    debouncedSearchFn(val);
    throttledSearchFn(val);
  };

  // Reset pagination cursor when filters change
  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    setCursor(null);
    setCursorHistory([null]);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [debouncedSearch, stockStatus, isActive]);

  // Clean up debounce on unmount
  useEffect(() => {
    return () => {
      debouncedSearchFn.cancel();
      throttledSearchFn.cancel();
    };
  }, [debouncedSearchFn, throttledSearchFn]);

  // Fetch products query
  const queryParams = useMemo(() => {
    return {
      limit: 8,
      cursor,
      search: debouncedSearch,
      stock_status: stockStatus === 'all' ? undefined : stockStatus,
      is_active: isActive === 'all' ? undefined : isActive === 'active',
    };
  }, [cursor, debouncedSearch, stockStatus, isActive]);

  const { data, isLoading, isError, error, refetch } = useProducts(queryParams);

  const products = data?.products || [];
  const hasNext = data?.has_next || false;

  // Pagination navigation handlers
  const handleNextPage = () => {
    if (hasNext && data?.next_cursor) {
      setCursorHistory((prev) => [...prev, data.next_cursor]);
      setCursor(data.next_cursor);
    }
  };

  const handlePrevPage = () => {
    if (cursorHistory.length > 1) {
      const newHistory = cursorHistory.slice(0, -1);
      setCursorHistory(newHistory);
      setCursor(newHistory[newHistory.length - 1]);
    }
  };

  // CRUD operation handlers
  const handleCreateOrUpdate = async (formData: FormData) => {
    try {
      if (editingProduct) {
        await updateProductMutation.mutateAsync({
          id: editingProduct.id,
          data: formData,
        });
        toast.success('Product updated successfully.');
      } else {
        await createProductMutation.mutateAsync(formData);
        toast.success('Product added successfully.');
      }
      setIsFormOpen(false);
      setEditingProduct(null);
    } catch (err) {
      const error = err as Error;
      toast.error(error.message || 'Failed to save product.');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this product?')) {
      try {
        await deleteProductMutation.mutateAsync(id);
        toast.success('Product deleted successfully.');
        // If current page empty, go back
        if (products.length === 1 && cursorHistory.length > 1) {
          handlePrevPage();
        }
      } catch (err) {
        const error = err as Error;
        toast.error(error.message || 'Failed to delete product.');
      }
    }
  };

  const handleOpenAddModal = () => {
    setEditingProduct(null);
    setIsFormOpen(true);
  };

  const handleOpenEditModal = (product: Product) => {
    setEditingProduct(product);
    setIsFormOpen(true);
  };

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-800">Products Catalog</h2>
          <p className="text-xs text-slate-400 font-medium mt-0.5">Manage inventory items, SKUs, pricing, and active status.</p>
        </div>
        <Button 
          onClick={handleOpenAddModal}
          className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold cursor-pointer h-10 px-4 gap-1.5 shadow-sm shadow-indigo-100 self-start md:self-auto"
        >
          <Plus className="w-4 h-4" />
          Add Product
        </Button>
      </div>

      {/* Filters & Search Toolbar */}
      <div className="flex flex-col gap-4 bg-white/80 backdrop-blur-md border border-indigo-100/50 p-4 rounded-2xl shadow-sm">
        <div className="flex flex-col lg:flex-row gap-3">
          {/* Lodash Debounced Search Bar */}
          <div className="flex-1 relative flex items-center">
            <Search className="absolute left-3 w-4 h-4 text-slate-400" />
            <Input 
              type="text"
              placeholder="Search by name, description or SKU..."
              value={searchInput}
              onChange={handleSearchChange}
              className="pl-9 pr-4 bg-slate-50 border-slate-200 focus:border-indigo-500 rounded-xl text-xs h-10"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Stock Filter */}
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-xl px-3 h-10">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select 
                value={stockStatus} 
                onChange={(e) => setStockStatus(e.target.value as 'all' | 'in_stock' | 'out_of_stock')}
                className="bg-transparent border-none text-slate-600 text-xs font-semibold focus:outline-none cursor-pointer pr-1"
              >
                <option value="all">All Inventory</option>
                <option value="in_stock">In Stock Only</option>
                <option value="out_of_stock">Out of Stock</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-xl px-3 h-10">
              <select 
                value={isActive} 
                onChange={(e) => setIsActive(e.target.value as 'all' | 'active' | 'inactive')}
                className="bg-transparent border-none text-slate-600 text-xs font-semibold focus:outline-none cursor-pointer"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active Only</option>
                <option value="inactive">Inactive Only</option>
              </select>
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-xl border border-slate-200/50">
              <button 
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg cursor-pointer transition-all ${viewMode === 'grid' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
                title="Grid View"
              >
                <Grid className="w-4 h-4" />
              </button>
              <button 
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-lg cursor-pointer transition-all ${viewMode === 'table' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}
                title="List/Table View"
              >
                <List className="w-4 h-4" />
              </button>
            </div>

            <Button
              variant="outline"
              onClick={() => refetch()}
              className="border-slate-200 hover:bg-slate-50 text-slate-500 hover:text-slate-700 h-10 w-10 p-0 rounded-xl cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {/* Lodash Throttling debug / analytics visual indicators */}
        {searchInput && (
          <div className="flex items-center gap-4 text-[10px] font-mono text-slate-400 font-semibold border-t border-slate-50 pt-2 px-1">
            <span>Debounced (API Search Query): <strong className="text-indigo-600">&quot;{debouncedSearch}&quot;</strong></span>
            <span className="hidden sm:inline">|</span>
            <span>Throttled (Immediate Logs): <strong className="text-amber-600">&quot;{throttledSearch}&quot;</strong></span>
          </div>
        )}
      </div>

      {/* Main Catalog View */}
      {isLoading ? (
        <div className="flex-1 flex flex-col items-center justify-center py-20 text-slate-400">
          <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3" />
          <span className="text-xs">Loading products...</span>
        </div>
      ) : isError ? (
        <div className="flex-1 flex flex-col items-center justify-center py-16 text-rose-500 bg-rose-50/50 rounded-2xl border border-rose-100/50 p-6 text-center">
          <AlertCircle className="w-8 h-8 mb-2" />
          <h4 className="text-sm font-bold">Failed to load catalog</h4>
          <p className="text-xs text-rose-400 mt-1 max-w-xs">{error?.message || 'Check database configurations.'}</p>
        </div>
      ) : products.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center py-20 text-center bg-white/50 border border-dashed border-indigo-100 rounded-2xl">
          <Package className="w-10 h-10 text-slate-300 mb-3" />
          <h4 className="text-sm font-bold text-slate-700">No Products Found</h4>
          <p className="text-xs text-slate-400 max-w-xs mt-1">
            No items matched your filters or search. Try adding a new product to your inventory!
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {products.map((product) => (
            <ProductCard 
              key={product.id}
              product={product}
              onEdit={handleOpenEditModal}
              onDelete={handleDelete}
              isDeleting={deleteProductMutation.isPending}
            />
          ))}
        </div>
      ) : (
        <ProductTable 
          products={products}
          onEdit={handleOpenEditModal}
          onDelete={handleDelete}
          isDeleting={deleteProductMutation.isPending}
        />
      )}

      {/* Pagination Footer */}
      {!isLoading && !isError && products.length > 0 && (
        <div className="flex items-center justify-between border-t border-slate-100 pt-4 px-2">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            Page {cursorHistory.length}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={cursorHistory.length === 1}
              onClick={handlePrevPage}
              className="border-slate-200 hover:bg-slate-50 text-slate-500 rounded-xl h-9 px-3 gap-1 cursor-pointer disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!hasNext}
              onClick={handleNextPage}
              className="border-slate-200 hover:bg-slate-50 text-slate-500 rounded-xl h-9 px-3 gap-1 cursor-pointer disabled:opacity-40"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Form Dialog Modal */}
      <ProductFormModal 
        key={isFormOpen ? (editingProduct?.id || 'new') : 'closed'}
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        product={editingProduct}
        onSubmit={handleCreateOrUpdate}
        isSubmitting={createProductMutation.isPending || updateProductMutation.isPending}
      />
    </div>
  );
}
